"""Фоновая задача анализа демки (выполняется RQ-воркером)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from analysis.errors import AnalysisError
from analysis.pipeline import analyze_demo

from .config import get_settings
from .db import Match, Report, get_sessionmaker, utcnow

log = logging.getLogger(__name__)

STAGE_PROGRESS_MIN_INTERVAL = 0.5  # секунд между записями прогресса в БД


def _update(match_id: str, **fields) -> None:
    with get_sessionmaker()() as db:
        db.query(Match).filter(Match.id == match_id).update(fields)
        db.commit()


def analyze_match_job(match_id: str, path: str) -> None:
    """Анализирует демку, сохраняет отчёты всех игроков и удаляет файл демки."""
    last = {"t": 0.0}

    def progress(pct: int, stage: str) -> None:
        now = time.monotonic()
        if now - last["t"] >= STAGE_PROGRESS_MIN_INTERVAL:
            last["t"] = now
            _update(match_id, progress=int(pct), stage=stage)

    _update(match_id, status="processing", progress=1, stage="start")
    try:
        result = analyze_demo(path, progress=progress)
        with get_sessionmaker()() as db:
            match = db.get(Match, match_id)
            if match is None:  # матч удалили, пока шёл анализ
                return
            players = []
            for p in result["players"]:
                report = Report(match_id=match_id, steamid=p["steamid"], name=p["name"], data=result["reports"][p["steamid"]])
                db.add(report)
                db.flush()
                players.append({**p, "report_id": report.id})
            match.players = players
            match.meta = result["match"]
            match.status = "done"
            match.progress = 100
            match.stage = "done"
            match.finished_at = utcnow()
            db.commit()
    except AnalysisError as exc:
        log.info("analysis failed for %s: %s", match_id, exc.code)
        _update(match_id, status="failed", stage="failed", error_code=exc.code, error_message=exc.message, finished_at=utcnow())
    except Exception:
        log.exception("unexpected error while analysing %s", match_id)
        _update(
            match_id,
            status="failed",
            stage="failed",
            error_code="internal",
            error_message="Внутренняя ошибка при анализе демки. Попробуйте ещё раз позже.",
            finished_at=utcnow(),
        )
    finally:
        Path(path).unlink(missing_ok=True)  # демку на сервере не храним


def enqueue_analysis(match_id: str, path: str, background=None) -> None:
    settings = get_settings()
    if settings.task_mode == "inline":
        if background is not None:
            background.add_task(analyze_match_job, match_id, path)
        else:
            analyze_match_job(match_id, path)
        return
    from redis import Redis
    from rq import Queue

    queue = Queue("analysis", connection=Redis.from_url(settings.redis_url))
    queue.enqueue(
        analyze_match_job,
        match_id,
        path,
        job_timeout=settings.job_timeout_seconds,
        result_ttl=3600,
        failure_ttl=86400,
    )
