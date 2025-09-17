from django import template
from babel.dates import format_date

register = template.Library()

@register.filter
def ru_date(value, fmt="d MMMM yyyy"):
    """
    Форматирует дату на русском с помощью Babel.
    Пример: {{ my_date|ru_date:"d MMMM yyyy" }}
    """
    if not value:
        return ""
    try:
        return format_date(value, format=fmt, locale="ru")
    except Exception:
        return str(value)