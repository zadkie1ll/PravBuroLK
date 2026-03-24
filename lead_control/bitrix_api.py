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
    return f"D_{deal_id}"


def _extract_crm_bindings(task_data: dict) -> set[str]:
    raw_bindings = (
        task_data.get("ufCrmTask")
        or task_data.get("UF_CRM_TASK")
        or task_data.get("uf_crm_task")
        or []
    )

    if isinstance(raw_bindings, str):
        raw_bindings = [raw_bindings]

    return {str(item) for item in raw_bindings if item}


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
    binding = _get_deal_binding(deal_id)
    deal_id_str = str(deal_id)
    return (
        binding in _extract_crm_bindings(task_data)
        or deal_id_str in _extract_deal_specific_bindings(task_data)
    )


def ensure_task_bound_to_deal(task_id: int, deal_id: int) -> None:
    binding = _get_deal_binding(deal_id)
    task_data = get_task_by_id(task_id)

    if _is_task_bound_to_deal(task_data, deal_id):
        return

    update_attempts = [
        {
            "taskId": task_id,
            "fields": {
                "UF_CRM_TASK": [binding],
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
                "UF_CRM_TASK": [binding],
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

    raise BitrixAPIError(
        f"Task {task_id} was created, but deal binding {binding} was not saved"
    )


def _create_task(
    *,
    title: str,
    description: str,
    responsible_id: int,
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

    if auditor_id:
        fields["AUDITORS"] = [auditor_id]

    if deal_id:
        fields["UF_CRM_TASK"] = [_get_deal_binding(deal_id)]
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
    auditor_id: int | None = None,
    title: str,
    description: str,
    deadline: str,
) -> int:
    return _create_task(
        title=title,
        description=description,
        responsible_id=responsible_id,
        auditor_id=auditor_id,
        deal_id=deal_id,
        deadline=deadline,
    )


def create_bitrix_task(
    title: str,
    description: str,
    responsible_id: int,
    auditor_id: int | None = None,
    deal_id: int | None = None,
) -> int:
    """
    Создает задачу в Bitrix24 и возвращает ее ID.
    """
    return _create_task(
        title=title,
        description=description,
        responsible_id=responsible_id,
        auditor_id=auditor_id,
        deal_id=deal_id,
    )
