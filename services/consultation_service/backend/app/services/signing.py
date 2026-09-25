from __future__ import annotations

import base64
import hashlib
import hmac


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _salted_hmac(key_salt: str, value: str, secret: str, algorithm: str = "sha256") -> hmac.HMAC:
    hasher = getattr(hashlib, algorithm)
    key = hasher(key_salt.encode() + secret.encode()).digest()
    return hmac.new(key, msg=value.encode(), digestmod=hasher)


def _base64_hmac(salt: str, value: str, key: str, algorithm: str = "sha256") -> str:
    return _b64_encode(_salted_hmac(salt, value, key, algorithm=algorithm).digest())


class BadSignature(Exception):
    pass


class Signer:
    """Тот же приём, что services/documents_service/backend/app/services/django_signing.py
    (порт django.core.signing.Signer) — здесь не обязан быть байт-в-байт совместим с монолитом,
    т.к. эта страница никогда в нём не жила, но реализация проверенная, поэтому переиспользуем.
    """

    def __init__(self, key: str, salt: str, sep: str = ":", algorithm: str = "sha256"):
        self.key = key
        self.salt = salt
        self.sep = sep
        self.algorithm = algorithm

    def _signature(self, value: str) -> str:
        return _base64_hmac(self.salt + "signer", value, self.key, algorithm=self.algorithm)

    def sign(self, value: str) -> str:
        return f"{value}{self.sep}{self._signature(value)}"

    def unsign(self, signed_value: str) -> str:
        if self.sep not in signed_value:
            raise BadSignature("no separator found in value")
        value, sig = signed_value.rsplit(self.sep, 1)
        if not hmac.compare_digest(sig, self._signature(value)):
            raise BadSignature("signature does not match")
        return value
