"""Хранение чанков загрузки на диске.

Каждый чанк — отдельный файл <upload_dir>/<upload_id>/<index>.chunk: так параллельные
и повторные запросы не мешают друг другу, а полнота проверяется по набору файлов.
После сборки чанки удаляются; собранная демка удаляется воркером после анализа.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from .config import Settings

DEMO_TTL_SECONDS = 6 * 3600


def upload_path(settings: Settings, upload_id: str) -> Path:
    return settings.upload_dir / upload_id


def demo_path(settings: Settings, match_id: str) -> Path:
    return settings.upload_dir / f"{match_id}.dem"


def chunk_file(settings: Settings, upload_id: str, index: int) -> Path:
    return upload_path(settings, upload_id) / f"{index:06d}.chunk"


def write_chunk(settings: Settings, upload_id: str, index: int, data: bytes) -> None:
    path = chunk_file(settings, upload_id, index)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)  # атомарно: чанк либо целиком есть, либо его нет


def missing_chunks(settings: Settings, upload_id: str, total: int) -> list[int]:
    return [i for i in range(total) if not chunk_file(settings, upload_id, i).exists()]


def assemble(settings: Settings, upload_id: str, total: int, target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as out:
        for i in range(total):
            with chunk_file(settings, upload_id, i).open("rb") as f:
                shutil.copyfileobj(f, out, 1024 * 1024)
    remove_upload(settings, upload_id)
    return target.stat().st_size


def remove_upload(settings: Settings, upload_id: str) -> None:
    shutil.rmtree(upload_path(settings, upload_id), ignore_errors=True)


def cleanup_stale(settings: Settings) -> int:
    """Удаляет брошенные загрузки (старше upload_ttl_minutes) и забытые демки (старше 6 ч)."""
    if not settings.upload_dir.exists():
        return 0
    cutoff = time.time() - settings.upload_ttl_minutes * 60
    # Собранные демки могут ждать в очереди — их держим дольше (воркер удаляет их сам).
    demo_cutoff = time.time() - DEMO_TTL_SECONDS
    removed = 0
    for entry in settings.upload_dir.iterdir():
        try:
            limit = demo_cutoff if entry.suffix == ".dem" else cutoff
            if entry.stat().st_mtime >= limit:
                continue
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
            removed += 1
        except FileNotFoundError:
            continue
    return removed
