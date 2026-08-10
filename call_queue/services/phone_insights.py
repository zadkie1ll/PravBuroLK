from __future__ import annotations

from dataclasses import dataclass
import json
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import phonenumbers
from phonenumbers import geocoder, timezone as phone_timezone
from django.utils import timezone


@dataclass(frozen=True)
class PhoneInsightRule:
    prefix: str
    region_label: str
    timezone_name: str


RUSSIAN_PREFIX_RULES = [
    PhoneInsightRule("7495", "Москва", "Europe/Moscow"),
    PhoneInsightRule("7499", "Москва", "Europe/Moscow"),
    PhoneInsightRule("7812", "Санкт-Петербург", "Europe/Moscow"),
    PhoneInsightRule("7861", "Краснодарский край", "Europe/Moscow"),
    PhoneInsightRule("7863", "Ростовская область", "Europe/Moscow"),
    PhoneInsightRule("7342", "Пермский край", "Asia/Yekaterinburg"),
    PhoneInsightRule("7343", "Свердловская область", "Asia/Yekaterinburg"),
    PhoneInsightRule("7347", "Республика Башкортостан", "Asia/Yekaterinburg"),
    PhoneInsightRule("7351", "Челябинская область", "Asia/Yekaterinburg"),
    PhoneInsightRule("7381", "Омская область", "Asia/Omsk"),
    PhoneInsightRule("7383", "Новосибирская область", "Asia/Novosibirsk"),
    PhoneInsightRule("7385", "Алтайский край", "Asia/Barnaul"),
    PhoneInsightRule("7391", "Красноярский край", "Asia/Krasnoyarsk"),
    PhoneInsightRule("7421", "Хабаровский край", "Asia/Vladivostok"),
    PhoneInsightRule("7423", "Приморский край", "Asia/Vladivostok"),
    PhoneInsightRule("7424", "Сахалинская область", "Asia/Sakhalin"),
    PhoneInsightRule("7415", "Камчатский край", "Asia/Kamchatka"),
]


TIMEZONE_LABELS = {
    "Europe/Moscow": "МСК",
    "Asia/Yekaterinburg": "UTC+5",
    "Asia/Omsk": "UTC+6",
    "Asia/Novosibirsk": "UTC+7",
    "Asia/Barnaul": "UTC+7",
    "Asia/Krasnoyarsk": "UTC+7",
    "Asia/Vladivostok": "UTC+10",
    "Asia/Sakhalin": "UTC+11",
    "Asia/Kamchatka": "UTC+12",
}


REGION_TIMEZONE_KEYWORDS = [
    ("москва", "Europe/Moscow"),
    ("московск", "Europe/Moscow"),
    ("санкт-петербург", "Europe/Moscow"),
    ("ленинград", "Europe/Moscow"),
    ("калининград", "Europe/Kaliningrad"),
    ("удмурт", "Europe/Samara"),
    ("самар", "Europe/Samara"),
    ("астрахан", "Europe/Astrakhan"),
    ("саратов", "Europe/Saratov"),
    ("ульянов", "Europe/Ulyanovsk"),
    ("волгоград", "Europe/Volgograd"),
    ("ханты", "Asia/Yekaterinburg"),
    ("сургут", "Asia/Yekaterinburg"),
    ("ямало", "Asia/Yekaterinburg"),
    ("абзелил", "Asia/Yekaterinburg"),
    ("белорец", "Asia/Yekaterinburg"),
    ("свердлов", "Asia/Yekaterinburg"),
    ("челябин", "Asia/Yekaterinburg"),
    ("тюмен", "Asia/Yekaterinburg"),
    ("башкорт", "Asia/Yekaterinburg"),
    ("перм", "Asia/Yekaterinburg"),
    ("оренбург", "Asia/Yekaterinburg"),
    ("курган", "Asia/Yekaterinburg"),
    ("омск", "Asia/Omsk"),
    ("кемеров", "Asia/Novokuznetsk"),
    ("новосибир", "Asia/Novosibirsk"),
    ("томск", "Asia/Tomsk"),
    ("алтай", "Asia/Barnaul"),
    ("тыва", "Asia/Krasnoyarsk"),
    ("тува", "Asia/Krasnoyarsk"),
    ("хакас", "Asia/Krasnoyarsk"),
    ("краснояр", "Asia/Krasnoyarsk"),
    ("иркут", "Asia/Irkutsk"),
    ("бурят", "Asia/Irkutsk"),
    ("забайкаль", "Asia/Chita"),
    ("якут", "Asia/Yakutsk"),
    ("амур", "Asia/Yakutsk"),
    ("примор", "Asia/Vladivostok"),
    ("хабаров", "Asia/Vladivostok"),
    ("еврейск", "Asia/Vladivostok"),
    ("сахалин", "Asia/Sakhalin"),
    ("магадан", "Asia/Magadan"),
    ("камчат", "Asia/Kamchatka"),
    ("чукот", "Asia/Anadyr"),
]


@lru_cache(maxsize=1)
def load_def_9xx_ranges() -> dict[str, list[dict[str, int | str]]]:
    path = Path(__file__).resolve().parent / "data" / "def_9xx_ranges.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_russian_phone_digits(phone: str, *, preserve_toll_free_8: bool = False) -> str:
    raw = str(phone or "").strip()
    if not raw:
        return ""

    fallback_digits = "".join(ch for ch in raw if ch.isdigit())
    if preserve_toll_free_8 and fallback_digits.startswith("8800") and len(fallback_digits) >= 11:
        return fallback_digits[:11]

    try:
        parsed = phonenumbers.parse(raw, "RU")
        if parsed.country_code == 7 and phonenumbers.is_possible_number(parsed):
            return f"7{str(parsed.national_number).zfill(10)}"
    except phonenumbers.NumberParseException:
        pass

    if len(fallback_digits) >= 11 and fallback_digits.startswith("8"):
        return f"7{fallback_digits[1:11]}"
    if len(fallback_digits) >= 11 and fallback_digits.startswith("7"):
        return fallback_digits[:11]
    if len(fallback_digits) >= 10 and fallback_digits.startswith("9"):
        return f"7{fallback_digits[:10]}"
    if len(fallback_digits) == 10:
        return f"7{fallback_digits}"
    return fallback_digits


def infer_timezone_by_region(region_label: str) -> str:
    normalized = str(region_label or "").strip().lower()
    for keyword, timezone_name in REGION_TIMEZONE_KEYWORDS:
        if keyword in normalized:
            return timezone_name
    return "Europe/Moscow"


def get_timezone_label(timezone_name: str) -> str:
    if not timezone_name:
        return ""
    current_dt = timezone.now()
    local_offset = current_dt.astimezone(ZoneInfo(timezone_name)).utcoffset()
    moscow_offset = current_dt.astimezone(ZoneInfo("Europe/Moscow")).utcoffset()
    if local_offset is None or moscow_offset is None:
        return timezone_name
    diff_hours = int((local_offset - moscow_offset).total_seconds() // 3600)
    if diff_hours == 0:
        return "МСК"
    sign = "+" if diff_hours > 0 else ""
    return f"МСК{sign}{diff_hours}"


def lookup_mobile_region_by_json(digits: str) -> tuple[str, str]:
    if len(digits) != 11 or not digits.startswith("79"):
        return "", ""
    def_code = digits[1:4]
    number_tail = int(digits[4:])
    ranges = load_def_9xx_ranges().get(def_code, [])
    for item in ranges:
        start = int(item.get("start", -1))
        end = int(item.get("end", -1))
        if start <= number_tail <= end:
            region_label = str(item.get("region") or "").strip()
            timezone_name = infer_timezone_by_region(region_label)
            return region_label, timezone_name
    return "", ""


def build_phone_insights(phone: str) -> dict[str, str | bool]:
    digits = normalize_russian_phone_digits(phone)
    result = {
        "region_label": "",
        "timezone_label": "",
        "local_time": "",
        "is_estimated": False,
    }
    if not digits:
        return result
    if digits.startswith("7") and len(digits) == 11:
        region_label, timezone_name = lookup_mobile_region_by_json(digits)
        if region_label:
            local_dt = timezone.now().astimezone(ZoneInfo(timezone_name))
            result.update(
                {
                    "region_label": region_label,
                    "timezone_label": get_timezone_label(timezone_name),
                    "local_time": local_dt.strftime("%H:%M"),
                    "is_estimated": False,
                }
            )
            return result
        try:
            parsed = phonenumbers.parse(f"+{digits}", "RU")
            if phonenumbers.is_possible_number(parsed):
                region_label = geocoder.description_for_number(parsed, "ru")
                timezones = phone_timezone.time_zones_for_number(parsed)
                timezone_name = timezones[0] if len(timezones) == 1 else ""
                if timezone_name == "Etc/Unknown":
                    timezone_name = ""
                if digits[1] == "9" and region_label == "Россия":
                    region_label = "Мобильный номер РФ"
                if region_label or timezone_name:
                    local_time = ""
                    timezone_label = ""
                    if timezone_name:
                        local_dt = timezone.now().astimezone(ZoneInfo(timezone_name))
                        local_time = local_dt.strftime("%H:%M")
                        timezone_label = get_timezone_label(timezone_name)
                    result.update(
                        {
                            "region_label": region_label or "Россия",
                            "timezone_label": timezone_label,
                            "local_time": local_time,
                            "is_estimated": False,
                        }
                    )
                    return result
        except phonenumbers.NumberParseException:
            pass
        for rule in RUSSIAN_PREFIX_RULES:
            if digits.startswith(rule.prefix):
                local_dt = timezone.now().astimezone(ZoneInfo(rule.timezone_name))
                result.update(
                    {
                        "region_label": f"{rule.region_label} (ориентировочно)",
                        "timezone_label": get_timezone_label(rule.timezone_name),
                        "local_time": local_dt.strftime("%H:%M"),
                        "is_estimated": True,
                    }
                )
                return result
        if digits[1] == "9":
            result.update(
                {
                    "region_label": "Мобильный номер РФ",
                    "timezone_label": "",
                    "local_time": "",
                    "is_estimated": True,
                }
            )
            return result
    return result
