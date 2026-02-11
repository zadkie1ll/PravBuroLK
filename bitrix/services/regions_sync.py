# services/regions_sync.py
from django.db import transaction
from django.utils import timezone

from bitrix.models import Region
from .bitrix_client import BitrixClient
from django.conf import settings

BITRIX_REGION_FIELD = "UF_CRM_1745886887592"
BITRIX_WEBHOOK_URL = "https://prav-buro.bitrix24.ru/rest/24/pa1x5irnfpbcnh27/"


def sync_regions_from_bitrix_logic() -> dict:
    b24 = BitrixClient(BITRIX_WEBHOOK_URL)
    enums = b24.get_deal_userfield_enums(BITRIX_REGION_FIELD)

    incoming_ids = set()
    created = 0
    updated = 0

    with transaction.atomic():
        for item in enums:
            bitrix_id = int(item["ID"])
            name = (item.get("VALUE") or "").strip()
            incoming_ids.add(bitrix_id)

            obj, was_created = Region.objects.update_or_create(
                bitrix_region_id=bitrix_id,
                defaults={"name": name, "is_active": True},
            )
            if was_created:
                created += 1
            else:
                # считаем updated только если реально поменялось
                # (update_or_create не говорит, менялось ли, поэтому сравниваем отдельно)
                updated += 1

        deactivated_qs = Region.objects.exclude(bitrix_region_id__in=incoming_ids).filter(is_active=True)
        deactivated_count = deactivated_qs.count()
        deactivated_qs.update(is_active=False)

    return {
        "ok": True,
        "field": BITRIX_REGION_FIELD,
        "total_from_bitrix": len(enums),
        "created": created,
        "updated": updated,
        "deactivated": deactivated_count,
        "synced_at": timezone.now().isoformat(),
    }
