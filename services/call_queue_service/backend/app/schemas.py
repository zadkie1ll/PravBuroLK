from datetime import date

from pydantic import BaseModel

from .models import CallEntityType


class RegisterRequest(BaseModel):
    # Не EmailStr: логин не всегда настоящий email (например, тестовые аккаунты
    # вроде "test-manager", заведённые напрямую в базе).
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class BuildQueueRequest(BaseModel):
    """Соответствует ProductionRecallForm (call_queue/forms.py)."""

    entity_type: CallEntityType = CallEntityType.DEAL
    date_from: date
    date_to: date
    stage_id: str = ""
    auto_dial: bool = True


class AddCustomItemRequest(BaseModel):
    """Соответствует CustomQueueAddForm (call_queue/forms.py)."""

    entity_type: CallEntityType = CallEntityType.DEAL
    query: str
    category_id: str = ""


class ChoiceOut(BaseModel):
    value: str
    label: str


class QueueStateOut(BaseModel):
    queue: list[dict]
    queue_size: int
    current_index: int
    current_item: dict | None
    manager_name: str
    entity_type: str
    auto_dial_enabled: bool
    stage_choices: list[ChoiceOut]
    category_choices: list[ChoiceOut]


class ResolveCallRequest(BaseModel):
    """Соответствует production_handler_resolve (call_queue/views.py:1198)."""

    callid: str
    decision: str


class AutoNextRequest(BaseModel):
    """Соответствует production_handler_auto_next (call_queue/views.py:1253)."""

    completed_callid: str
    force_resume: bool = False


class CallSnapshotOut(BaseModel):
    ok: bool = True
    snapshot: dict
    item: dict


class ResolveCallOut(BaseModel):
    ok: bool = True
    decision: str
    bitrix_url: str = ""
    item: dict


class AutoNextOut(BaseModel):
    ok: bool = True
    started: bool = False
    call_id: str = ""
    redirect_url: str = ""
    no_next: bool = False
    hold_for_manager: bool = False
    await_manager_decision: bool = False
    already_processed: bool = False
