import logging

from django.conf import settings
import requests


logger = logging.getLogger(__name__)


class BitrixAPIError(Exception):
    pass


def _get_webhook_url() -> str:
    return getattr(settings, "BITRIX_WEBHOOK_URL", "").rstrip("/")


def _build_url(method_name: str) -> str:
    base = _get_webhook_url()
    return f"{base}/{method_name}.json"


def _post(method_name: str, payload: dict) -> dict:
    url = _build_url(method_name)
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise BitrixAPIError(
            f"{data.get('error')}: {data.get('error_description')}"
        )

    return data


def _flatten_form_payload(payload: dict, prefix: str = "") -> dict:
    flat = {}

    for key, value in payload.items():
        full_key = f"{prefix}[{key}]" if prefix else str(key)

        if isinstance(value, dict):
            flat.update(_flatten_form_payload(value, full_key))
            continue

        if isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                list_key = f"{full_key}[{index}]"
                if isinstance(item, dict):
                    flat.update(_flatten_form_payload(item, list_key))
                else:
                    flat[list_key] = item
            continue

        flat[full_key] = value

    return flat


def _post_form(method_name: str, payload: dict) -> dict:
    url = _build_url(method_name)
    response = requests.post(
        url,
        data=_flatten_form_payload(payload),
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise BitrixAPIError(
            f"{data.get('error')}: {data.get('error_description')}"
        )

    return data


def get_deal_by_id(deal_id: int) -> dict:
    data = _post("crm.deal.get", {"id": deal_id})
    result = data.get("result")
    if not result:
        raise BitrixAPIError(f"Deal {deal_id} not found")
    return result


def find_deals_by_contact_and_category(
    contact_id: int,
    category_id: int,
    *,
    exclude_deal_id: int | None = None,
) -> list[dict]:
    data = _post(
        "crm.deal.list",
        {
            "filter": {
                "CONTACT_ID": contact_id,
                "CATEGORY_ID": category_id,
            },
            "order": {"ID": "DESC"},
            "select": ["ID", "CONTACT_ID", "CATEGORY_ID", "STAGE_ID"],
        },
    )
    deals = data.get("result") or []
    if exclude_deal_id is None:
        return deals
    exclude_id_str = str(exclude_deal_id)
    return [deal for deal in deals if str(deal.get("ID")) != exclude_id_str]


_DEAL_COPY_SKIP_FIELDS = (
    "ID",
    "CATEGORY_ID",
    "STAGE_ID",
    "STAGE_SEMANTIC_ID",
    "DATE_CREATE",
    "DATE_MODIFY",
    "MOVED_BY_ID",
    "MOVED_TIME",
    "LAST_ACTIVITY_BY",
    "LAST_ACTIVITY_TIME",
    "ORIGIN_ID",
    "ORIGINATOR_ID",
)


def create_deal(fields: dict) -> int:
    data = _post("crm.deal.add", {"fields": fields})
    deal_id = data.get("result")
    if not deal_id:
        raise BitrixAPIError("Failed to create deal")
    return deal_id


def duplicate_deal_to_agents_category(deal_data: dict) -> int | None:
    """
    Если сделка перешла в стадию "Сделка успешна" (C2:WON) в категории
    "Сопровождение", создаёт копию карточки в категории "Агенты" на её
    первой стадии — если сделки этого контакта там ещё нет.
    Возвращает ID новой сделки, либо None, если копия не создавалась.
    """
    source_category_id = settings.DEAL_DUPLICATION_SOURCE_CATEGORY_ID
    source_won_stage_id = settings.DEAL_DUPLICATION_SOURCE_WON_STAGE_ID
    target_category_id = settings.DEAL_DUPLICATION_TARGET_CATEGORY_ID
    target_first_stage_id = settings.DEAL_DUPLICATION_TARGET_FIRST_STAGE_ID

    if str(deal_data.get("CATEGORY_ID")) != str(source_category_id):
        return None
    if deal_data.get("STAGE_ID") != source_won_stage_id:
        return None

    contact_id = deal_data.get("CONTACT_ID")
    if not contact_id:
        return None

    existing = find_deals_by_contact_and_category(contact_id, target_category_id)
    if existing:
        return None

    fields = {
        key: value
        for key, value in deal_data.items()
        if key not in _DEAL_COPY_SKIP_FIELDS
    }
    fields["CATEGORY_ID"] = target_category_id
    fields["STAGE_ID"] = target_first_stage_id

    return create_deal(fields)


def get_task_by_id(task_id: int) -> dict:
    data = _post("tasks.task.get", {"taskId": task_id})
    result = data.get("result") or {}
    task = result.get("task")

    if not task:
        raise BitrixAPIError(f"Task {task_id} not found")

    return task


def is_task_completed(task_data: dict) -> bool:
    """
    В Bitrix завершенная задача обычно имеет status = 5
    """
    return str(task_data.get("status")) == "5"


def _extract_task_id(result) -> int:
    if isinstance(result, dict):
        task_id = result.get("task", {}).get("id") or result.get("id")
    else:
        task_id = result

    if not task_id:
        raise BitrixAPIError("Task ID not found in Bitrix response")

    return int(task_id)


def _get_deal_binding(deal_id: int) -> str:
    return f"CRM_DEAL_{deal_id}"


def _get_deal_bindings(deal_id: int) -> list[str]:
    return [_get_deal_binding(deal_id), f"D_{deal_id}"]


def _extract_crm_bindings(task_data: dict) -> set[str]:
    raw_bindings = (
        task_data.get("ufCrmTask")
        or task_data.get("UF_CRM_TASK")
        or task_data.get("uf_crm_task")
        or []
    )

    if isinstance(raw_bindings, str):
        raw_bindings = [raw_bindings]

    bindings = set()
    for item in raw_bindings:
        if not item:
            continue
        if isinstance(item, dict):
            for value in item.values():
                if value:
                    bindings.add(str(value))
            continue
        bindings.add(str(item))
    return bindings


def _extract_deal_specific_bindings(task_data: dict) -> set[str]:
    raw_bindings = (
        task_data.get("ufCrmTaskDeal")
        or task_data.get("UF_CRM_TASK_DEAL")
        or task_data.get("uf_crm_task_deal")
        or []
    )

    if isinstance(raw_bindings, (str, int)):
        raw_bindings = [raw_bindings]

    return {str(item) for item in raw_bindings if item is not None}


def _is_task_bound_to_deal(task_data: dict, deal_id: int) -> bool:
    deal_id_str = str(deal_id)
    crm_bindings = _extract_crm_bindings(task_data)
    return (
        any(binding in crm_bindings for binding in _get_deal_bindings(deal_id))
        or deal_id_str in _extract_deal_specific_bindings(task_data)
    )


def ensure_task_bound_to_deal(task_id: int, deal_id: int) -> None:
    bindings = _get_deal_bindings(deal_id)
    task_data = get_task_by_id(task_id)

    if _is_task_bound_to_deal(task_data, deal_id):
        return

    update_attempts = [
        {
            "taskId": task_id,
            "fields": {
                "UF_CRM_TASK": bindings,
            },
        },
        {
            "taskId": task_id,
            "fields": {
                "UF_CRM_TASK": [bindings[0]],
            },
        },
        {
            "taskId": task_id,
            "fields": {
                "UF_CRM_TASK": [bindings[1]],
            },
        },
        {
            "taskId": task_id,
            "fields": {
                "UF_CRM_TASK_DEAL": [str(deal_id)],
            },
        },
        {
            "taskId": task_id,
            "fields": {
                "UF_CRM_TASK": bindings,
                "UF_CRM_TASK_DEAL": [str(deal_id)],
            },
        },
    ]

    for payload in update_attempts:
        try:
            _post("tasks.task.update", payload)
        except BitrixAPIError:
            logger.exception(
                "Bitrix JSON update failed while binding task_id=%s to deal_id=%s",
                task_id,
                deal_id,
            )

        refreshed_task_data = get_task_by_id(task_id)
        if _is_task_bound_to_deal(refreshed_task_data, deal_id):
            return

        try:
            _post_form("tasks.task.update", payload)
        except BitrixAPIError:
            logger.exception(
                "Bitrix form update failed while binding task_id=%s to deal_id=%s",
                task_id,
                deal_id,
            )

        refreshed_task_data = get_task_by_id(task_id)
        if _is_task_bound_to_deal(refreshed_task_data, deal_id):
            return

    logger.warning(
        "Task %s was created, but deal binding was not confirmed for deal_id=%s. "
        "Expected one of %s or UF_CRM_TASK_DEAL=%s. Last task data keys: %s",
        task_id,
        deal_id,
        bindings,
        deal_id,
        sorted(task_data.keys()),
    )


def _create_task(
    *,
    title: str,
    description: str,
    responsible_id: int,
    created_by_id: int | None = None,
    auditor_id: int | None = None,
    deal_id: int | None = None,
    deadline: str | None = None,
) -> int:
    fields = {
        "TITLE": title,
        "DESCRIPTION": description or "",
        "RESPONSIBLE_ID": responsible_id,
    }

    if deadline:
        fields["DEADLINE"] = deadline

    if created_by_id:
        fields["CREATED_BY"] = created_by_id

    if auditor_id:
        fields["AUDITORS"] = [auditor_id]

    if deal_id:
        fields["UF_CRM_TASK"] = _get_deal_bindings(deal_id)
        fields["UF_CRM_TASK_DEAL"] = [str(deal_id)]

    data = _post("tasks.task.add", {"fields": fields})
    task_id = _extract_task_id(data.get("result"))

    if deal_id:
        ensure_task_bound_to_deal(task_id, deal_id)

    return task_id


def create_typical_task(
    *,
    deal_id: int,
    responsible_id: int,
    created_by_id: int | None = None,
    auditor_id: int | None = None,
    title: str,
    description: str,
    deadline: str,
) -> int:
    return _create_task(
        title=title,
        description=description,
        responsible_id=responsible_id,
        created_by_id=created_by_id,
        auditor_id=auditor_id,
        deal_id=deal_id,
        deadline=deadline,
    )


def create_bitrix_task(
    title: str,
    description: str,
    responsible_id: int,
    created_by_id: int | None = None,
    auditor_id: int | None = None,
    deal_id: int | None = None,
    deadline: str | None = None,
) -> int:
    """
    Создает задачу в Bitrix24 и возвращает ее ID.
    """
    return _create_task(
        title=title,
        description=description,
        responsible_id=responsible_id,
        created_by_id=created_by_id,
        auditor_id=auditor_id,
        deal_id=deal_id,
        deadline=deadline,
    )
