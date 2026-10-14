"""HTTP API.

Загрузка демки чанками:
  POST /api/uploads                       {filename, size} -> {upload_id, chunk_size, total_chunks}
  PUT  /api/uploads/{id}/chunks/{index}   тело = сырые байты чанка
  POST /api/uploads/{id}/complete         -> {match_id}  (ставит анализ в очередь)
Результаты:
  GET  /api/matches/{id}                  статус/прогресс, после анализа — 10 игроков со ссылками на отчёты
  GET  /api/reports/{report_id}           отчёт игрока (публичная ссылка)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import PurePath

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from analysis.errors import AnalysisError
from analysis.loader import check_demo_header

from . import storage
from .config import Settings, get_settings
from .db import Match, Report, Upload, get_db, init_db, utcnow
from .ratelimit import make_upload_limiter
from .tasks import enqueue_analysis

log = logging.getLogger(__name__)


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    app.state.upload_limiter = make_upload_limiter(settings)
    yield


app = FastAPI(title="CS2 Demo Analyzer API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class CreateUpload(BaseModel):
    filename: str = Field(max_length=255)
    size: int = Field(gt=0)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def public_config(settings: Settings = Depends(get_settings)):
    return {"max_upload_mb": settings.max_upload_mb, "chunk_size": settings.chunk_size}


@app.post("/api/uploads", status_code=201)
def create_upload(
    body: CreateUpload,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not body.filename.lower().endswith(".dem"):
        raise api_error(400, "bad_extension", "Нужен файл демки с расширением .dem.")
    if body.size > settings.max_upload_bytes:
        raise api_error(413, "too_large", f"Файл больше {settings.max_upload_mb} МБ.")
    if not request.app.state.upload_limiter.hit(client_ip(request, settings)):
        raise api_error(429, "rate_limited", "Слишком много загрузок. Попробуйте через час.")
    storage.cleanup_stale(settings)

    upload = Upload(
        ip=client_ip(request, settings),
        filename=PurePath(body.filename).name[:255],
        size=body.size,
        chunk_size=settings.chunk_size,
    )
    db.add(upload)
    db.commit()
    return {"upload_id": upload.id, "chunk_size": upload.chunk_size, "total_chunks": upload.total_chunks}


def _active_upload(db: Session, upload_id: str) -> Upload:
    upload = db.get(Upload, upload_id)
    if upload is None or upload.status != "uploading":
        raise api_error(404, "upload_not_found", "Загрузка не найдена или уже завершена.")
    return upload


@app.put("/api/uploads/{upload_id}/chunks/{index}")
async def upload_chunk(
    upload_id: str,
    index: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    upload = _active_upload(db, upload_id)
    total = upload.total_chunks
    if not 0 <= index < total:
        raise api_error(400, "bad_chunk", "Неверный номер чанка.")
    expected = upload.chunk_size if index < total - 1 else upload.size - upload.chunk_size * (total - 1)

    data = bytearray()
    async for part in request.stream():
        data += part
        if len(data) > expected:
            raise api_error(413, "bad_chunk", "Чанк больше заявленного размера.")
    if len(data) != expected:
        raise api_error(400, "bad_chunk", "Размер чанка не совпадает с ожидаемым.")

    if index == 0:  # проверяем заголовок демки сразу, а не после загрузки 500 МБ
        try:
            check_demo_header(bytes(data[:16]))
        except AnalysisError as exc:
            upload.status = "failed"
            db.commit()
            storage.remove_upload(settings, upload_id)
            raise api_error(400, exc.code, exc.message) from exc

    storage.write_chunk(settings, upload_id, index, bytes(data))
    return {"ok": True, "index": index}


@app.post("/api/uploads/{upload_id}/complete", status_code=202)
def complete_upload(
    upload_id: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    upload = _active_upload(db, upload_id)
    missing = storage.missing_chunks(settings, upload_id, upload.total_chunks)
    if missing:
        raise api_error(400, "incomplete", f"Не хватает чанков: {missing[:10]}")

    match = Match(filename=upload.filename)
    db.add(match)
    db.flush()
    path = storage.demo_path(settings, match.id)
    size = storage.assemble(settings, upload_id, upload.total_chunks, path)
    if size != upload.size:
        path.unlink(missing_ok=True)
        raise api_error(400, "incomplete", "Размер собранного файла не совпадает с заявленным.")
    upload.status = "complete"
    db.commit()

    enqueue_analysis(match.id, str(path), background)
    return {"match_id": match.id}


def _stale(match: Match, settings: Settings) -> bool:
    created = match.created_at if match.created_at.tzinfo else match.created_at.replace(tzinfo=UTC)
    limit = timedelta(seconds=settings.job_timeout_seconds + 600)
    return match.status in ("queued", "processing") and datetime.now(UTC) - created > limit


@app.get("/api/matches/{match_id}")
def get_match(match_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    match = db.get(Match, match_id)
    if match is None:
        raise api_error(404, "match_not_found", "Анализ не найден.")
    if _stale(match, settings):  # воркер упал (например, OOM) и не обновил статус
        match.status, match.stage = "failed", "failed"
        match.error_code = "timeout"
        match.error_message = "Анализ не завершился вовремя. Попробуйте загрузить демку ещё раз."
        match.finished_at = utcnow()
        db.commit()
    error = {"code": match.error_code, "message": match.error_message} if match.status == "failed" else None
    return {
        "id": match.id,
        "status": match.status,
        "progress": match.progress,
        "stage": match.stage,
        "filename": match.filename,
        "error": error,
        "match": match.meta,
        "players": match.players or [],
    }


@app.get("/api/reports/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if report is None:
        raise api_error(404, "report_not_found", "Отчёт не найден.")
    match = db.get(Match, report.match_id)
    return {
        "id": report.id,
        "match_id": report.match_id,
        "created_at": report.created_at.isoformat(),
        "players": (match.players if match else None) or [],
        "report": report.data,
    }


@app.get("/api/matches/{match_id}/players/{steamid}")
def find_player_report(match_id: str, steamid: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.match_id == match_id, Report.steamid == steamid).one_or_none()
    if report is None:
        raise api_error(404, "player_not_found", "Игрок с таким SteamID не найден в этой демке.")
    return {"report_id": report.id}
