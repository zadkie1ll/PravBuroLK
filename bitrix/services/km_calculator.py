from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Literal


IncomeType = Literal["SALARY", "PENSION", "MIXED", "NONE"]
PmType = Literal["WORKING", "PENSIONER", "NONE"]


def _to_decimal(val: Any) -> Decimal:
    """
    Приводит bitrix-значения к Decimal.
    Поддерживает:
      - None
      - "224000|RUB"
      - "228 000.00"
      - числа
    """
    if val is None:
        return Decimal("0")

    s = str(val).strip()

    # bitrix money like "224000|RUB"
    if "|" in s:
        s = s.split("|", 1)[0].strip()

    # remove currency / spaces
    s = (
        s.replace("₽", "")
        .replace("Р", "")
        .replace(" ", "")
        .replace("\xa0", "")
        .replace(",", ".")
        .strip()
    )

    if s == "" or s.lower() in ("нет", "none", "null"):
        return Decimal("0")

    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def _clamp_non_negative(x: Decimal) -> Decimal:
    return x if x > 0 else Decimal("0")


@dataclass(frozen=True)
class KmInput:
    region_bitrix_id: Optional[int]  # можно хранить для логов/отладки
    salary: Any
    pension: Any
    children_count: Any

    # не входят в КМ (по ТЗ) — считаем и возвращаем справочно
    benefits: Any = 0
    child_payments: Any = 0
    alimony: Any = 0
    social: Any = 0
    other: Any = 0


@dataclass(frozen=True)
class PmValues:
    """
    ПМ для региона (уже достали из БД в handler).
    """
    pm_working: Any
    pm_pensioner: Any
    pm_child: Any = 0  # можно 0, если не используешь


def calculate_km(inp: KmInput, pm: PmValues) -> Dict[str, Any]:
    """
    Формула по ТЗ:
    keep = PM(по типу дохода) + PM_CHILD * children_count
    contest_mass = max(0, base_income - keep)

    Тип ПМ:
      - зарплата -> pm_working
      - пенсия -> pm_pensioner
      - зарплата+пенсия -> pm_working
    """

    salary = _clamp_non_negative(_to_decimal(inp.salary))
    pension = _clamp_non_negative(_to_decimal(inp.pension))
    children_count_raw = _to_decimal(inp.children_count)
    # дети — целое и неотрицательное
    children_count = int(children_count_raw) if children_count_raw > 0 else 0

    base_income = salary + pension

    # доходы "не входят" — справочно
    benefits = _clamp_non_negative(_to_decimal(inp.benefits))
    child_payments = _clamp_non_negative(_to_decimal(inp.child_payments))
    alimony = _clamp_non_negative(_to_decimal(inp.alimony))
    social = _clamp_non_negative(_to_decimal(inp.social))
    other = _clamp_non_negative(_to_decimal(inp.other))
    excluded_total = benefits + child_payments + alimony + social + other

    # определяем тип дохода
    if salary > 0 and pension > 0:
        income_type: IncomeType = "MIXED"
    elif salary > 0:
        income_type = "SALARY"
    elif pension > 0:
        income_type = "PENSION"
    else:
        income_type = "NONE"

    pm_working = _clamp_non_negative(_to_decimal(pm.pm_working))
    pm_pensioner = _clamp_non_negative(_to_decimal(pm.pm_pensioner))
    pm_child = _clamp_non_negative(_to_decimal(pm.pm_child))

    warnings = []

    if income_type in ("SALARY", "MIXED"):
        pm_base = pm_working
        pm_type: PmType = "WORKING"
        if pm_working == 0:
            warnings.append("pm_working_is_zero_or_missing")
    elif income_type == "PENSION":
        pm_base = pm_pensioner
        pm_type = "PENSIONER"
        if pm_pensioner == 0:
            warnings.append("pm_pensioner_is_zero_or_missing")
    else:
        pm_base = Decimal("0")
        pm_type = "NONE"
        warnings.append("income_is_zero_or_missing")

    keep_amount = pm_base + (pm_child * Decimal(children_count))

    # сколько уходит в конкурсную массу
    contest_mass = _clamp_non_negative(base_income - keep_amount)

    # сколько остаётся должнику из base_income
    remain_to_person = base_income - contest_mass  # эквивалент min(base_income, keep_amount)

    return {
        "region_bitrix_id": inp.region_bitrix_id,

        "income_type": income_type,
        "pm_type": pm_type,

        "inputs": {
            "salary": float(salary),
            "pension": float(pension),
            "children_count": children_count,
            "excluded": {
                "benefits": float(benefits),
                "child_payments": float(child_payments),
                "alimony": float(alimony),
                "social": float(social),
                "other": float(other),
                "excluded_total": float(excluded_total),
            },
        },

        "pm": {
            "pm_working": float(pm_working),
            "pm_pensioner": float(pm_pensioner),
            "pm_child": float(pm_child),
            "pm_base_used": float(pm_base),
        },

        "result": {
            "base_income": float(base_income),
            "keep_amount": float(keep_amount),
            "remain_to_person": float(remain_to_person),
            "contest_mass": float(contest_mass),
        },

        "warnings": warnings,
    }
