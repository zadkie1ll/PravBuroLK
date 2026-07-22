from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user_flexible
from ..db import get_db
from ..models import Course, Module, ModuleMaterial, User
from ..services.file_streaming import resolve_media_path, stream_file_range
from .courses import _user_can_access_course

router = APIRouter(tags=["files"])


@router.get("/modules/{module_id}/video")
def module_video_file(
    module_id: int,
    request: Request,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    module = (
        db.query(Module)
        .options(joinedload(Module.course).joinedload(Course.departments))
        .filter(Module.id == module_id, Module.is_active.is_(True))
        .first()
    )
    if not module or not module.course.is_active or not _user_can_access_course(current_user, module.course):
        raise HTTPException(status_code=404, detail="Модуль не найден")
    if not module.private_video:
        raise HTTPException(status_code=404, detail="Видео не найдено")

    content_type = mimetypes.guess_type(module.private_video)[0] or "application/octet-stream"
    filename = module.private_video.rsplit("/", 1)[-1]
    full_path = resolve_media_path(module.private_video)
    return stream_file_range(request, full_path, content_type, filename)


@router.get("/materials/{material_id}/file")
def module_material_file(
    material_id: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    material = (
        db.query(ModuleMaterial)
        .options(joinedload(ModuleMaterial.module).joinedload(Module.course).joinedload(Course.departments))
        .filter(ModuleMaterial.id == material_id, ModuleMaterial.is_active.is_(True))
        .first()
    )
    if (
        not material
        or not material.module.is_active
        or not material.module.course.is_active
        or not _user_can_access_course(current_user, material.module.course)
    ):
        raise HTTPException(status_code=404, detail="Материал не найден")

    content_type = mimetypes.guess_type(material.file)[0] or "application/pdf"
    filename = material.file.rsplit("/", 1)[-1]
    full_path = resolve_media_path(material.file)
    return FileResponse(
        full_path,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )
