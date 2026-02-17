from django.db import transaction
from django.utils import timezone

from bitrix.services.bitrix_client import BitrixClient
from leadreport.models import LeadSource

BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"

BITRIX_SOURCE_ENTITY = "SOURCE"


def sync_sources_from_bitrix_logic() -> dict:
    b24 = BitrixClient(BITRIX_WEBHOOK_URL)

    items = b24.get_status_list(BITRIX_SOURCE_ENTITY)

    incoming_ids: set[int] = set()
    created = 0
    updated = 0

    with transaction.atomic():
        for item in items:
            bitrix_id_raw = item.get("ID")
            if bitrix_id_raw is None:
                continue

            bitrix_id = int(bitrix_id_raw)
            name = (item.get("NAME") or "").strip()

            incoming_ids.add(bitrix_id)

            _, was_created = LeadSource.objects.update_or_create(
                bitrix_id=bitrix_id,
                defaults={"name": name, "is_active": True},
            )
            if was_created:
                created += 1
            else:
                updated += 1

        deactivated_qs = LeadSource.objects.exclude(bitrix_id__in=incoming_ids).filter(is_active=True)
        deactivated_count = deactivated_qs.count()
        deactivated_qs.update(is_active=False)

    return {
        "ok": True,
        "entity": BITRIX_SOURCE_ENTITY,
        "total_from_bitrix": len(items),
        "created": created,
        "updated": updated,
        "deactivated": deactivated_count,
        "synced_at": timezone.now().isoformat(),
    }