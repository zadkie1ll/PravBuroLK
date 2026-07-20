from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import CallEntityType, User, UserQueueState
from .social_links import with_social_desktop_links


def get_state(db: Session, user: User) -> UserQueueState:
    state = db.get(UserQueueState, user.id)
    if not state:
        state = UserQueueState(user_id=user.id, queue_json=[], queue_index=0)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def get_queue(db: Session, user: User) -> list[dict]:
    return list(get_state(db, user).queue_json or [])


def save_queue(db: Session, user: User, queue: list[dict]) -> None:
    state = get_state(db, user)
    state.queue_json = queue
    db.commit()


def get_queue_index(state: UserQueueState, queue: list[dict]) -> int:
    if not queue:
        return 0
    return max(0, min(state.queue_index, len(queue) - 1))


def get_current_item(db: Session, user: User) -> tuple[list[dict], int, dict | None]:
    state = get_state(db, user)
    queue = list(state.queue_json or [])
    if not queue:
        return queue, 0, None
    index = get_queue_index(state, queue)
    return queue, index, queue[index]


def build_queue(db: Session, user: User, *, entity_type: str, items: list[dict]) -> list[dict]:
    """Соответствует action=build_queue: сохраняет добавленные вручную custom-элементы,
    заменяет остальные результатами нового поиска по датам."""
    state = get_state(db, user)
    kept_custom_items = [item for item in (state.queue_json or []) if item.get("source") == "custom"]
    custom_keys = {(item.get("entity_type"), item.get("entity_id")) for item in kept_custom_items}
    fetched_items = [
        with_social_desktop_links({**item, "status": "pending", "manual_decision": "", "call_id": ""})
        for item in items
        if (item.get("entity_type"), item.get("entity_id")) not in custom_keys
    ]
    queue = kept_custom_items + fetched_items
    state.queue_json = queue
    state.queue_index = 0
    state.entity_type = entity_type
    db.commit()
    return queue


def append_custom_items(db: Session, user: User, items: list[dict]) -> int:
    state = get_state(db, user)
    queue = list(state.queue_json or [])
    existing_keys = {(item.get("entity_type"), item.get("entity_id")) for item in queue}
    added = 0
    for item in items:
        key = (item.get("entity_type"), item.get("entity_id"))
        if key in existing_keys:
            continue
        queue.append(
            with_social_desktop_links(
                {**item, "status": "pending", "manual_decision": "", "call_id": "", "source": "custom"}
            )
        )
        existing_keys.add(key)
        added += 1
    if added:
        state.queue_json = queue
        if len(queue) == added:
            state.queue_index = 0
        db.commit()
    return added


def remove_item(db: Session, user: User, index: int) -> dict | None:
    state = get_state(db, user)
    queue = list(state.queue_json or [])
    if not queue or not (0 <= index < len(queue)):
        return None
    removed = queue.pop(index)
    state.queue_json = queue
    state.queue_index = max(0, min(state.queue_index, len(queue) - 1)) if queue else 0
    db.commit()
    return removed


def reset_queue(db: Session, user: User) -> None:
    state = get_state(db, user)
    state.queue_json = []
    state.queue_index = 0
    db.commit()


def mark_current_item(db: Session, user: User, **updates: Any) -> dict | None:
    state = get_state(db, user)
    queue = list(state.queue_json or [])
    index = get_queue_index(state, queue)
    if not queue:
        return None
    return mark_item(db, user, index, **updates)


def mark_item(db: Session, user: User, index: int, **updates: Any) -> dict | None:
    """Соответствует mark_prod_item (call_queue/views.py:560) — правит элемент по индексу,
    не обязательно текущий (нужно для production_handler_auto_next, который метит следующий)."""
    state = get_state(db, user)
    queue = list(state.queue_json or [])
    if not queue or index < 0 or index >= len(queue):
        return None
    queue[index] = {**queue[index], **updates}
    state.queue_json = queue
    db.commit()
    return queue[index]


def find_item_index_by_call_id(db: Session, user: User, call_id: str) -> int | None:
    queue = get_queue(db, user)
    for idx, item in enumerate(queue):
        if item.get("call_id") == call_id:
            return idx
    return None
