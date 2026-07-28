from __future__ import annotations

from itsdangerous import BadSignature, URLSafeSerializer

from ..config import settings

_serializer = URLSafeSerializer(settings.django_secret_key, salt="documents.contract.session")


def read_flags(raw_cookie: str | None) -> dict[str, bool]:
    if not raw_cookie:
        return {}
    try:
        data = _serializer.loads(raw_cookie)
    except BadSignature:
        return {}
    return data if isinstance(data, dict) else {}


def write_flags(flags: dict[str, bool]) -> str:
    return _serializer.dumps(flags)
