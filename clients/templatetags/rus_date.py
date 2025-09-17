from django import template
from babel.dates import format_date
import datetime

register = template.Library()

@register.filter
def rus_date(value, fmt="d MMMM y"):
    """
    Форматирует дату или datetime на русском языке с помощью Babel.
    fmt — формат Babel (например: 'd MMMM y' -> '17 сентября 2025').
    """
    if not value:
        return ""

    # Если пришёл datetime — берём только date
    if isinstance(value, datetime.datetime):
        value = value.date()

    # Если пришёл что-то вроде numpy.datetime64 или ещё что-то —
    # приводим к стандартному date через strptime/strftime
    if not isinstance(value, datetime.date):
        raise ValueError("rus_date filter requires a date or datetime object")

    # Babel нормально принимает объект date без tzinfo
    return format_date(value, format=fmt, locale='ru')