from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..db import get_db
from ..models import Click, UrlShortener
from ..schemas import (
    CreateSourcePayload,
    DeleteDestinationPayload,
    DestinationStat,
    MutationResponse,
    SourceStat,
    StatsResponse,
    UpdateDestinationPayload,
    UpdateSourcePayload,
)

router = APIRouter(prefix="/api", tags=["stats"], dependencies=[Depends(require_staff)])


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Порт urlshorter/views.py:show_stats (GET-часть) — группировка по destination."""
    rows = (
        db.query(UrlShortener, func.count(Click.id).label("click_count"))
        .outerjoin(Click, Click.url_id == UrlShortener.id)
        .group_by(UrlShortener.id)
        .order_by(UrlShortener.destination, UrlShortener.source)
        .all()
    )

    grouped: dict[str, list[SourceStat]] = defaultdict(list)
    for obj, click_count in rows:
        grouped[obj.destination].append(SourceStat(source=obj.source, clicks=click_count))

    stats = [
        DestinationStat(destination=dest, sources=sources, total_clicks=sum(s.clicks for s in sources))
        for dest, sources in sorted(grouped.items())
    ]
    return StatsResponse(stats=stats)


@router.post("/sources", response_model=MutationResponse)
def create_source(payload: CreateSourcePayload, db: Session = Depends(get_db)):
    """Порт add_new_destination/add_source веток show_stats — обе создают одну и ту же
    строку UrlShortener, разница была только в тексте формы."""
    source = payload.source.strip()
    destination = payload.destination.strip()
    if not source or not destination:
        raise HTTPException(status_code=400, detail="Заполните оба поля.")

    existing = db.query(UrlShortener).filter(UrlShortener.source == source).first()
    if existing is not None:
        if existing.destination == destination:
            # Повтор той же самой заявки (двойной клик, ретрай после таймаута) —
            # источник уже создан с тем же назначением, отдаём успех, а не ошибку.
            return MutationResponse(success=True, message=f'Источник "{source}" уже добавлен.')
        raise HTTPException(status_code=409, detail="Источник с таким кодом уже существует.")

    db.add(UrlShortener(source=source, destination=destination))
    try:
        db.commit()
    except IntegrityError:
        # Гонка: кто-то создал тот же source между нашей проверкой и commit.
        db.rollback()
        raise HTTPException(status_code=409, detail="Источник с таким кодом уже существует.")

    return MutationResponse(success=True, message=f'Источник "{source}" добавлен.')


@router.put("/sources/{source}", response_model=MutationResponse)
def update_source(source: str, payload: UpdateSourcePayload, db: Session = Depends(get_db)):
    """Порт edit_source ветки show_stats."""
    obj = db.query(UrlShortener).filter(UrlShortener.source == source).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Источник не найден.")

    new_source = payload.new_source.strip()
    new_destination = payload.new_destination.strip()
    if not new_source or not new_destination:
        raise HTTPException(status_code=400, detail="Заполните оба поля.")

    if new_source != obj.source and db.query(UrlShortener).filter(UrlShortener.source == new_source).first():
        raise HTTPException(status_code=409, detail="Новый код источника уже занят.")

    obj.source = new_source
    obj.destination = new_destination
    db.commit()

    return MutationResponse(success=True, message=f'Источник обновлён: "{new_source}" → "{new_destination}".')


@router.delete("/sources/{source}", response_model=MutationResponse)
def delete_source(source: str, db: Session = Depends(get_db)):
    """Порт delete_source ветки show_stats."""
    obj = db.query(UrlShortener).filter(UrlShortener.source == source).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Источник не найден.")

    db.delete(obj)
    db.commit()
    return MutationResponse(success=True, message=f'Источник "{source}" удалён.')


@router.put("/destinations", response_model=MutationResponse)
def update_destination(payload: UpdateDestinationPayload, db: Session = Depends(get_db)):
    """Порт edit_destination ветки show_stats — меняет URL для всех источников внутри."""
    old_destination = payload.old_destination
    new_destination = payload.new_destination.strip()
    if not new_destination or old_destination == new_destination:
        raise HTTPException(status_code=400, detail="Нет источников для изменения.")

    updated_count = (
        db.query(UrlShortener)
        .filter(UrlShortener.destination == old_destination)
        .update({UrlShortener.destination: new_destination})
    )
    db.commit()
    if not updated_count:
        raise HTTPException(status_code=404, detail="Нет источников для изменения.")

    return MutationResponse(success=True, message=f"URL назначения изменён для {updated_count} источников.")


@router.delete("/destinations", response_model=MutationResponse)
def delete_destination(payload: DeleteDestinationPayload, db: Session = Depends(get_db)):
    """Порт delete_destination ветки show_stats — удаляет все источники назначения."""
    deleted_count = (
        db.query(UrlShortener).filter(UrlShortener.destination == payload.destination).delete()
    )
    db.commit()
    if not deleted_count:
        raise HTTPException(status_code=404, detail="Ничего не удалено.")

    return MutationResponse(success=True, message=f"Назначение и {deleted_count} источников удалено.")
