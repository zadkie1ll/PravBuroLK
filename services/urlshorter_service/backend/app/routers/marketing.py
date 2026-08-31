from __future__ import annotations

import csv
import io
import re
import secrets
import string
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..db import get_db
from ..models import BOT_PREVIEW_USER_AGENTS, BotBlock, MarketingClick, MarketingLink, UtmMedium, UtmSource
from ..schemas import (
    AddBotBlockPayload,
    AddDictionaryValuePayload,
    BotBlockItem,
    CreateMarketingLinkPayload,
    CreateMarketingLinkResponse,
    DictionariesResponse,
    DictionaryItem,
    KnownValuesResponse,
    MarketingLinkOut,
    MarketingStatsResponse,
    MarketingStatsRow,
    MutationResponse,
)

router = APIRouter(prefix="/api/marketing", tags=["marketing"], dependencies=[Depends(require_staff)])
redirect_router = APIRouter(tags=["marketing-redirect"])

BOT_BASE_URL = "https://t.me/pravburohelpBot"
SOURCE_ALPHABET = string.ascii_lowercase + string.digits
UTM_FREE_TEXT_RE = re.compile(r"^[a-z0-9-]+$")

GROUP_BY_FIELDS = {
    "full_link": None,
    "utm_source": UtmSource.code,
    "utm_medium": UtmMedium.code,
    "utm_campaign": MarketingLink.utm_campaign,
    "utm_content": MarketingLink.utm_content,
    "utm_term": MarketingLink.utm_term,
    "link_type": MarketingLink.link_type,
    "destination": MarketingLink.destination,
    "bot_block": BotBlock.key,
}


def _validate_free_text(value: str, field: str):
    if value and not UTM_FREE_TEXT_RE.match(value):
        raise HTTPException(status_code=400, detail=f"{field}: разрешены только латиница, цифры и дефис.")


def _generate_unique_source(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(SOURCE_ALPHABET) for _ in range(7))
        if not db.query(MarketingLink).filter(MarketingLink.source == code).first():
            return code


def _build_destination_with_utm(link: MarketingLink) -> str:
    if link.link_type == "bot":
        parts = [link.bot_block.key, link.utm_source.code, link.utm_medium.code, link.utm_campaign]
        return f"{BOT_BASE_URL}?start=" + "_".join(parts)

    params = {}
    if link.link_type == "site":
        params["utm_source"] = link.utm_source.code
        params["utm_medium"] = link.utm_medium.code
    params["utm_campaign"] = link.utm_campaign
    if link.utm_content:
        params["utm_content"] = link.utm_content
    if link.utm_term:
        params["utm_term"] = link.utm_term

    separator = "&" if "?" in link.destination else "?"
    return f"{link.destination}{separator}{urlencode(params)}"


def _public_link(link: MarketingLink, request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/go?source={link.source}"


def _link_out(link: MarketingLink, request: Request) -> MarketingLinkOut:
    return MarketingLinkOut(
        id=link.id,
        source=link.source,
        link_type=link.link_type,
        destination=link.destination,
        utm_source=link.utm_source.code,
        utm_medium=link.utm_medium.code,
        utm_campaign=link.utm_campaign,
        utm_content=link.utm_content,
        utm_term=link.utm_term,
        bot_block=link.bot_block.key if link.bot_block else None,
        public_link=_public_link(link, request),
    )


@router.get("/dictionaries", response_model=DictionariesResponse)
def get_dictionaries(all_values: bool = False, db: Session = Depends(get_db)):
    src_q = db.query(UtmSource)
    med_q = db.query(UtmMedium)
    block_q = db.query(BotBlock)
    if not all_values:
        src_q = src_q.filter(UtmSource.is_active.is_(True))
        med_q = med_q.filter(UtmMedium.is_active.is_(True))
        block_q = block_q.filter(BotBlock.is_active.is_(True))

    return DictionariesResponse(
        utm_sources=[DictionaryItem(id=s.id, code=s.code, is_active=s.is_active) for s in src_q.order_by(UtmSource.code)],
        utm_mediums=[DictionaryItem(id=m.id, code=m.code, is_active=m.is_active) for m in med_q.order_by(UtmMedium.code)],
        bot_blocks=[
            BotBlockItem(id=b.id, key=b.key, title=b.title, is_active=b.is_active) for b in block_q.order_by(BotBlock.key)
        ],
    )


@router.post("/dictionaries/utm-sources", response_model=DictionaryItem)
def add_utm_source(payload: AddDictionaryValuePayload, db: Session = Depends(get_db)):
    code = payload.code.strip().lower()
    _validate_free_text(code, "code")
    if not code:
        raise HTTPException(status_code=400, detail="Пустое значение.")
    existing = db.query(UtmSource).filter(UtmSource.code == code).first()
    if existing:
        return DictionaryItem(id=existing.id, code=existing.code, is_active=existing.is_active)
    obj = UtmSource(code=code)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DictionaryItem(id=obj.id, code=obj.code, is_active=obj.is_active)


@router.patch("/dictionaries/utm-sources/{item_id}/toggle", response_model=DictionaryItem)
def toggle_utm_source(item_id: int, db: Session = Depends(get_db)):
    obj = db.query(UtmSource).filter(UtmSource.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Не найдено.")
    obj.is_active = not obj.is_active
    db.commit()
    return DictionaryItem(id=obj.id, code=obj.code, is_active=obj.is_active)


@router.post("/dictionaries/utm-mediums", response_model=DictionaryItem)
def add_utm_medium(payload: AddDictionaryValuePayload, db: Session = Depends(get_db)):
    code = payload.code.strip().lower()
    _validate_free_text(code, "code")
    if not code:
        raise HTTPException(status_code=400, detail="Пустое значение.")
    existing = db.query(UtmMedium).filter(UtmMedium.code == code).first()
    if existing:
        return DictionaryItem(id=existing.id, code=existing.code, is_active=existing.is_active)
    obj = UtmMedium(code=code)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DictionaryItem(id=obj.id, code=obj.code, is_active=obj.is_active)


@router.patch("/dictionaries/utm-mediums/{item_id}/toggle", response_model=DictionaryItem)
def toggle_utm_medium(item_id: int, db: Session = Depends(get_db)):
    obj = db.query(UtmMedium).filter(UtmMedium.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Не найдено.")
    obj.is_active = not obj.is_active
    db.commit()
    return DictionaryItem(id=obj.id, code=obj.code, is_active=obj.is_active)


@router.post("/dictionaries/bot-blocks", response_model=BotBlockItem)
def add_bot_block(payload: AddBotBlockPayload, db: Session = Depends(get_db)):
    key = payload.key.strip().lower()
    title = payload.title.strip()
    _validate_free_text(key, "key")
    if not key or not title:
        raise HTTPException(status_code=400, detail="Заполните ключ и название.")
    existing = db.query(BotBlock).filter(BotBlock.key == key).first()
    if existing:
        return BotBlockItem(id=existing.id, key=existing.key, title=existing.title, is_active=existing.is_active)
    obj = BotBlock(key=key, title=title)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return BotBlockItem(id=obj.id, key=obj.key, title=obj.title, is_active=obj.is_active)


@router.patch("/dictionaries/bot-blocks/{item_id}/toggle", response_model=BotBlockItem)
def toggle_bot_block(item_id: int, db: Session = Depends(get_db)):
    obj = db.query(BotBlock).filter(BotBlock.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Не найдено.")
    obj.is_active = not obj.is_active
    db.commit()
    return BotBlockItem(id=obj.id, key=obj.key, title=obj.title, is_active=obj.is_active)


@router.get("/known-values", response_model=KnownValuesResponse)
def known_values(db: Session = Depends(get_db)):
    def distinct(col):
        return [row[0] for row in db.query(col).filter(col != "").distinct().all()]

    return KnownValuesResponse(
        campaigns=distinct(MarketingLink.utm_campaign),
        contents=distinct(MarketingLink.utm_content),
        terms=distinct(MarketingLink.utm_term),
    )


@router.post("/links", response_model=CreateMarketingLinkResponse)
def create_link(payload: CreateMarketingLinkPayload, request: Request, db: Session = Depends(get_db)):
    if payload.link_type not in ("site", "bot", "other"):
        raise HTTPException(status_code=400, detail="Некорректный тип назначения.")

    utm_source = db.query(UtmSource).filter(UtmSource.id == payload.utm_source_id, UtmSource.is_active.is_(True)).first()
    utm_medium = db.query(UtmMedium).filter(UtmMedium.id == payload.utm_medium_id, UtmMedium.is_active.is_(True)).first()
    if not utm_source:
        raise HTTPException(status_code=400, detail="Выберите источник (utm_source).")
    if not utm_medium:
        raise HTTPException(status_code=400, detail="Выберите тип трафика (utm_medium).")

    utm_campaign = payload.utm_campaign.strip().lower()
    utm_content = payload.utm_content.strip().lower()
    utm_term = payload.utm_term.strip().lower()
    if not utm_campaign:
        raise HTTPException(status_code=400, detail="Заполните utm_campaign.")
    for field, value in (("utm_campaign", utm_campaign), ("utm_content", utm_content), ("utm_term", utm_term)):
        _validate_free_text(value, field)

    bot_block = None
    destination = (payload.destination or "").strip()
    if payload.link_type == "bot":
        bot_block = db.query(BotBlock).filter(BotBlock.id == payload.bot_block_id, BotBlock.is_active.is_(True)).first()
        if not bot_block:
            raise HTTPException(status_code=400, detail="Выберите блок бота.")
        destination = BOT_BASE_URL
    elif not destination:
        raise HTTPException(status_code=400, detail="Укажите целевую ссылку.")

    existing = (
        db.query(MarketingLink)
        .filter(
            MarketingLink.link_type == payload.link_type,
            MarketingLink.destination == destination,
            MarketingLink.utm_source_id == utm_source.id,
            MarketingLink.utm_medium_id == utm_medium.id,
            MarketingLink.utm_campaign == utm_campaign,
            MarketingLink.utm_content == utm_content,
            MarketingLink.utm_term == utm_term,
            MarketingLink.bot_block_id == (bot_block.id if bot_block else None),
        )
        .first()
    )
    if existing:
        return CreateMarketingLinkResponse(link=_link_out(existing, request), is_existing=True)

    link = MarketingLink(
        source=_generate_unique_source(db),
        link_type=payload.link_type,
        destination=destination,
        utm_source_id=utm_source.id,
        utm_medium_id=utm_medium.id,
        utm_campaign=utm_campaign,
        utm_content=utm_content,
        utm_term=utm_term,
        bot_block_id=bot_block.id if bot_block else None,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(MarketingLink)
            .filter(
                MarketingLink.link_type == payload.link_type,
                MarketingLink.destination == destination,
                MarketingLink.utm_source_id == utm_source.id,
                MarketingLink.utm_medium_id == utm_medium.id,
                MarketingLink.utm_campaign == utm_campaign,
                MarketingLink.utm_content == utm_content,
                MarketingLink.utm_term == utm_term,
                MarketingLink.bot_block_id == (bot_block.id if bot_block else None),
            )
            .first()
        )
        if existing:
            return CreateMarketingLinkResponse(link=_link_out(existing, request), is_existing=True)
        raise
    db.refresh(link)
    return CreateMarketingLinkResponse(link=_link_out(link, request), is_existing=False)


def _build_stats_query(
    db: Session,
    click_from: date | None,
    click_to: date | None,
    created_from: date | None,
    created_to: date | None,
    utm_source: str | None,
    utm_medium: str | None,
    utm_campaign: str | None,
    utm_content: str | None,
    utm_term: str | None,
    link_type: str | None,
    destination: str | None,
):
    q = (
        db.query(MarketingClick)
        .join(MarketingLink, MarketingClick.link_id == MarketingLink.id)
        .join(UtmSource, MarketingLink.utm_source_id == UtmSource.id)
        .join(UtmMedium, MarketingLink.utm_medium_id == UtmMedium.id)
        .outerjoin(BotBlock, MarketingLink.bot_block_id == BotBlock.id)
        .filter(MarketingClick.is_bot_preview.is_(False))
    )
    if click_from:
        q = q.filter(func.date(MarketingClick.clicked_at) >= click_from)
    if click_to:
        q = q.filter(func.date(MarketingClick.clicked_at) <= click_to)
    if created_from:
        q = q.filter(func.date(MarketingLink.created_at) >= created_from)
    if created_to:
        q = q.filter(func.date(MarketingLink.created_at) <= created_to)
    if utm_source:
        q = q.filter(UtmSource.code == utm_source)
    if utm_medium:
        q = q.filter(UtmMedium.code == utm_medium)
    if utm_campaign:
        q = q.filter(MarketingLink.utm_campaign == utm_campaign)
    if utm_content:
        q = q.filter(MarketingLink.utm_content == utm_content)
    if utm_term:
        q = q.filter(MarketingLink.utm_term == utm_term)
    if link_type:
        q = q.filter(MarketingLink.link_type == link_type)
    if destination:
        q = q.filter(MarketingLink.destination.ilike(f"%{destination}%"))
    return q


def _grouped_rows(db: Session, q, group_by: str) -> list[MarketingStatsRow]:
    if group_by == "full_link":
        sub = q.with_entities(MarketingClick.link_id, func.count(MarketingClick.id).label("clicks")).group_by(
            MarketingClick.link_id
        )
        counts = {row.link_id: row.clicks for row in sub.all()}
        if not counts:
            return []
        links = db.query(MarketingLink).filter(MarketingLink.id.in_(counts.keys())).all()
        rows = [
            MarketingStatsRow(group_value=_build_destination_with_utm(link), clicks=counts[link.id])
            for link in links
        ]
        return sorted(rows, key=lambda r: -r.clicks)

    field = GROUP_BY_FIELDS[group_by]
    sub = q.with_entities(field.label("group_value"), func.count(MarketingClick.id).label("clicks")).group_by(field)
    rows = [
        MarketingStatsRow(group_value=(row.group_value or "—"), clicks=row.clicks) for row in sub.all()
    ]
    return sorted(rows, key=lambda r: -r.clicks)


@router.get("/stats", response_model=MarketingStatsResponse)
def marketing_stats(
    db: Session = Depends(get_db),
    group_by: str = "full_link",
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    click_from: date | None = None,
    click_to: date | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    utm_content: str | None = None,
    utm_term: str | None = None,
    link_type: str | None = None,
    destination: str | None = None,
):
    if group_by not in GROUP_BY_FIELDS:
        raise HTTPException(status_code=400, detail="Некорректная группировка.")

    q = _build_stats_query(
        db, click_from, click_to, created_from, created_to,
        utm_source, utm_medium, utm_campaign, utm_content, utm_term, link_type, destination,
    )
    rows = _grouped_rows(db, q, group_by)
    total_clicks = sum(r.clicks for r in rows)
    total_rows = len(rows)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    page = min(page, total_pages)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]

    return MarketingStatsResponse(
        rows=page_rows, total_clicks=total_clicks, page=page, total_pages=total_pages, total_rows=total_rows
    )


@router.get("/stats/export.csv")
def export_stats_csv(
    db: Session = Depends(get_db),
    group_by: str = "full_link",
    click_from: date | None = None,
    click_to: date | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    utm_content: str | None = None,
    utm_term: str | None = None,
    link_type: str | None = None,
    destination: str | None = None,
):
    if group_by not in GROUP_BY_FIELDS:
        raise HTTPException(status_code=400, detail="Некорректная группировка.")

    q = _build_stats_query(
        db, click_from, click_to, created_from, created_to,
        utm_source, utm_medium, utm_campaign, utm_content, utm_term, link_type, destination,
    )
    rows = _grouped_rows(db, q, group_by)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([group_by, "clicks"])
    for row in rows:
        writer.writerow([row.group_value, row.clicks])
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=marketing_stats.csv"},
    )


CLICK_DEDUP_WINDOW = timedelta(seconds=3)


@redirect_router.get("/go")
def marketing_link_redirect(request: Request, source: str | None = None, db: Session = Depends(get_db)):
    if not source:
        raise HTTPException(status_code=400, detail="source is required")

    link = db.query(MarketingLink).filter(MarketingLink.source == source).first()
    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "") or ""
    is_bot_preview = any(bot_ua.lower() in user_agent.lower() for bot_ua in BOT_PREVIEW_USER_AGENTS)

    is_retry = (
        db.query(MarketingClick.id)
        .filter(
            MarketingClick.link_id == link.id,
            MarketingClick.ip_address == ip_address,
            MarketingClick.user_agent == user_agent,
            MarketingClick.clicked_at >= datetime.now(timezone.utc) - CLICK_DEDUP_WINDOW,
        )
        .first()
        is not None
    )
    if not is_retry:
        db.add(
            MarketingClick(
                link_id=link.id,
                ip_address=ip_address,
                user_agent=user_agent,
                is_bot_preview=is_bot_preview,
            )
        )
        db.commit()

    return RedirectResponse(_build_destination_with_utm(link), status_code=302)
