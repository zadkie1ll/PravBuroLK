from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import CallEntityType, User
from ..schemas import (
    AddCustomItemRequest,
    AutoNextOut,
    AutoNextRequest,
    BuildQueueRequest,
    CallSnapshotOut,
    ChoiceOut,
    QueueStateOut,
    ResolveCallOut,
    ResolveCallRequest,
)
from ..services import call_comments, queue_state
from ..services.bitrix.deal_service import BitrixDealService
from ..services.megafon_snapshot import build_megafon_call_snapshot
from ..services.telephony.megafon import MegafonAPIError, MegafonTelephonyService

router = APIRouter(prefix="/queue", tags=["queue"])


def _state_out(db: Session, user: User) -> QueueStateOut:
    state = queue_state.get_state(db, user)
    queue, index, current_item = queue_state.get_current_item(db, user)
    service = BitrixDealService()
    stage_choices = service.get_stage_choices(state.entity_type)
    category_choices = service.get_deal_category_choices() if state.entity_type == CallEntityType.DEAL.value else []
    return QueueStateOut(
        queue=queue,
        queue_size=len(queue),
        current_index=index,
        current_item=current_item,
        manager_name=user.sales_manager_name,
        entity_type=state.entity_type,
        auto_dial_enabled=state.auto_dial,
        stage_choices=[ChoiceOut(value=v, label=label) for v, label in stage_choices],
        category_choices=[ChoiceOut(value=v, label=label) for v, label in category_choices],
    )


@router.get("", response_model=QueueStateOut)
def get_queue_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _state_out(db, current_user)


@router.post("/build", response_model=QueueStateOut)
def build_queue(
    payload: BuildQueueRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Соответствует action=build_queue в call_queue/views.py:production_handler."""
    if payload.date_from > payload.date_to:
        raise HTTPException(status_code=400, detail="Дата начала не может быть позже даты окончания.")

    service = BitrixDealService()
    items = service.fetch_production_recall_deals(
        entity_type=payload.entity_type.value,
        date_from=payload.date_from,
        date_to=payload.date_to,
        stage_id=payload.stage_id,
    )
    queue_state.build_queue(db, current_user, entity_type=payload.entity_type.value, items=items)

    state = queue_state.get_state(db, current_user)
    state.date_from = payload.date_from.isoformat()
    state.date_to = payload.date_to.isoformat()
    state.stage_id = payload.stage_id
    state.auto_dial = payload.auto_dial
    db.commit()

    return _state_out(db, current_user)


@router.post("/add-custom", response_model=QueueStateOut)
def add_custom_item(
    payload: AddCustomItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Соответствует action=add_custom_item."""
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Введите номер телефона или имя клиента.")

    service = BitrixDealService()
    found_items = service.search_production_entities(
        entity_type=payload.entity_type.value,
        query=query,
        category_id=payload.category_id if payload.entity_type == CallEntityType.DEAL else "",
    )
    if not found_items:
        raise HTTPException(status_code=404, detail="По этому запросу ничего не найдено в Bitrix24.")

    added = queue_state.append_custom_items(db, current_user, found_items)

    state = queue_state.get_state(db, current_user)
    state.custom_entity_type = payload.entity_type.value
    state.custom_category_id = payload.category_id
    db.commit()

    if not added:
        raise HTTPException(status_code=409, detail="Найденные записи уже есть в очереди.")

    return _state_out(db, current_user)


@router.post("/reset", response_model=QueueStateOut)
def reset_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Соответствует action=reset_queue."""
    queue_state.reset_queue(db, current_user)
    return _state_out(db, current_user)


@router.post("/remove/{index}", response_model=QueueStateOut)
def remove_item(
    index: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Соответствует action=remove_item."""
    removed = queue_state.remove_item(db, current_user, index)
    if removed is None:
        raise HTTPException(status_code=404, detail="Элемент не найден в очереди.")
    return _state_out(db, current_user)


def _execute_megafon_call(user: User, phone: str, clid: str = "", show_phone: bool = True) -> tuple[str, dict]:
    """Соответствует execute_megafon_call (call_queue/views.py:569)."""
    telephony_service = MegafonTelephonyService()
    response = telephony_service.make_call(
        phone=phone,
        user=user.sales_manager_megafon_user or None,
        group=user.sales_manager_megafon_group or None,
        clid=clid or user.sales_manager_megafon_clid or None,
        show_phone=show_phone,
    )
    call_id = str(response.get("callid") or "")
    return call_id, response


@router.post("/start-call", response_model=QueueStateOut)
def start_call(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Соответствует action=start_call (call_queue/views.py:1086)."""
    queue, index, current_item = queue_state.get_current_item(db, current_user)
    if not current_item:
        raise HTTPException(status_code=400, detail="Сначала сформируйте очередь.")
    try:
        call_id, _response = _execute_megafon_call(current_user, current_item["phone"], show_phone=True)
    except MegafonAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось запустить звонок: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе в МегаФон АТС: {exc}") from exc
    queue_state.mark_item(db, current_user, index, call_id=call_id, status="calling", manual_decision="")
    return _state_out(db, current_user)


@router.get("/megafon/status", response_model=CallSnapshotOut)
def megafon_status(
    callid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Соответствует production_handler_status (call_queue/views.py:1180)."""
    queue = queue_state.get_queue(db, current_user)
    call_id = (callid or "").strip()
    current_item = next((item for item in queue if item.get("call_id") == call_id), None)
    if not call_id or not current_item:
        raise HTTPException(status_code=400, detail="callid is required")
    return CallSnapshotOut(snapshot=build_megafon_call_snapshot(db, call_id), item=current_item)


@router.post("/megafon/resolve", response_model=ResolveCallOut)
def megafon_resolve(
    payload: ResolveCallRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Соответствует production_handler_resolve (call_queue/views.py:1198)."""
    if payload.decision not in {"answered", "failed", "voicemail"}:
        raise HTTPException(status_code=400, detail="invalid decision")

    queue = queue_state.get_queue(db, current_user)
    item_index = next((idx for idx, item in enumerate(queue) if item.get("call_id") == payload.callid), None)
    if item_index is None:
        raise HTTPException(status_code=404, detail="call not found")

    bitrix_service = BitrixDealService()
    item = queue_state.mark_item(db, current_user, item_index, manual_decision=payload.decision, status=payload.decision)

    if payload.decision in {"failed", "voicemail"} and not item.get("comment_logged"):
        comment_line = (
            call_comments.format_voicemail_comment(current_user.sales_manager_name)
            if payload.decision == "voicemail"
            else call_comments.format_unanswered_comment(current_user.sales_manager_name)
        )
        updated_comments = bitrix_service.append_entity_comment(
            item.get("entity_type") or CallEntityType.DEAL.value,
            item.get("entity_id") or item.get("deal_id"),
            comment_line,
        )
        item = queue_state.mark_item(db, current_user, item_index, comment_logged=True, comments=updated_comments)

    bitrix_url = ""
    if payload.decision == "answered":
        bitrix_url = item.get("bitrix_url") or bitrix_service.build_entity_url(
            item.get("entity_type") or CallEntityType.DEAL.value,
            item.get("entity_id") or item.get("deal_id") or item.get("lead_id"),
        )

    return ResolveCallOut(decision=payload.decision, bitrix_url=bitrix_url, item=item)


@router.post("/megafon/auto-next", response_model=AutoNextOut)
def megafon_auto_next(
    payload: AutoNextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Соответствует production_handler_auto_next (call_queue/views.py:1253)."""
    completed_call_id = (payload.completed_callid or "").strip()
    if not completed_call_id:
        raise HTTPException(status_code=400, detail="completed_callid is required")

    snapshot = build_megafon_call_snapshot(db, completed_call_id)
    if not snapshot["latest_history_status"]:
        raise HTTPException(status_code=409, detail="call is not completed yet")

    state = queue_state.get_state(db, current_user)
    if state.last_completed_call_id == completed_call_id:
        return AutoNextOut(started=False, already_processed=True)

    queue = queue_state.get_queue(db, current_user)
    item_index = next((idx for idx, item in enumerate(queue) if item.get("call_id") == completed_call_id), None)
    if item_index is None:
        raise HTTPException(status_code=404, detail="call not found")

    item = queue[item_index]
    if snapshot["requires_manager_confirmation"] and item.get("manual_decision") not in {
        "answered",
        "failed",
        "voicemail",
    }:
        return AutoNextOut(started=False, await_manager_decision=True)

    if item.get("manual_decision") == "answered" and not payload.force_resume:
        state.last_completed_call_id = completed_call_id
        db.commit()
        return AutoNextOut(started=False, hold_for_manager=True)

    bitrix_service = BitrixDealService()
    if not item.get("comment_logged") and (
        item.get("manual_decision") == "failed"
        or snapshot["latest_history_status"] in {"Busy", "NotAvailable", "missed"}
    ):
        if snapshot["latest_history_status"] == "NotAvailable" and item.get("manual_decision") != "failed":
            comment_line = call_comments.format_unavailable_comment(current_user.sales_manager_name)
        else:
            comment_line = call_comments.format_unanswered_comment(current_user.sales_manager_name)
        updated_comments = bitrix_service.append_entity_comment(
            item.get("entity_type") or CallEntityType.DEAL.value,
            item.get("entity_id") or item.get("deal_id"),
            comment_line,
        )
        item = queue_state.mark_item(
            db,
            current_user,
            item_index,
            manual_decision="failed",
            status="failed",
            comment_logged=True,
            comments=updated_comments,
        )

    if item_index >= len(queue) - 1:
        state.last_completed_call_id = completed_call_id
        db.commit()
        return AutoNextOut(started=False, no_next=True)

    next_index = item_index + 1
    next_item = queue[next_index]
    try:
        next_call_id, _response = _execute_megafon_call(current_user, next_item["phone"], show_phone=True)
    except MegafonAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе в МегаФон АТС: {exc}") from exc

    state.queue_index = next_index
    state.last_completed_call_id = completed_call_id
    db.commit()
    queue_state.mark_item(db, current_user, next_index, call_id=next_call_id, status="calling", manual_decision="")

    return AutoNextOut(started=True, call_id=next_call_id)
