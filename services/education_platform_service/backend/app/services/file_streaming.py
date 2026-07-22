from __future__ import annotations

import os
import re
import uuid

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from ..config import settings

_RANGE_RE = re.compile(r"bytes=(\d+)-(\d*)")


def resolve_media_path(relative_path: str) -> str:
    full_path = os.path.join(settings.media_root, relative_path)
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    return full_path


def save_upload(upload: UploadFile, subdir: str) -> str:
    """Сохраняет UploadFile в media_root/{subdir}/{uuid}_{имя}, возвращает относительный путь
    (тот же вид, что и Django FileField.name — используется как есть в БД)."""
    directory = os.path.join(settings.media_root, subdir)
    os.makedirs(directory, exist_ok=True)
    safe_name = os.path.basename(upload.filename or "file")
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    full_path = os.path.join(directory, stored_name)
    with open(full_path, "wb") as destination:
        destination.write(upload.file.read())
    return f"{subdir}/{stored_name}"


def stream_file_range(request: Request, full_path: str, content_type: str, filename: str):
    """Порт _stream_file_range из education_platform/views.py:127-166 на FastAPI."""
    file_size = os.path.getsize(full_path)
    range_header = request.headers.get("range", "")
    range_match = _RANGE_RE.match(range_header)

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{filename}"',
        "Cache-Control": "private, no-store",
    }

    if not range_match:
        return FileResponse(full_path, media_type=content_type, headers=headers)

    start = int(range_match.group(1))
    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
    end = min(end, file_size - 1)
    length = end - start + 1

    def iterator():
        with open(full_path, "rb") as source:
            source.seek(start)
            remaining = length
            while remaining > 0:
                chunk = source.read(min(8192, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    return StreamingResponse(
        iterator(),
        status_code=206,
        media_type=content_type,
        headers=headers,
    )
