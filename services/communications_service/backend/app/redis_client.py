from __future__ import annotations

import redis

from .config import settings

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def acquire_dedupe_lock(dedupe_key: str, ttl_seconds: int = 60) -> bool:
    """Быстрый предохранитель от гонки при конкурентных ретраях одного и того же webhook'а
    (Bitrix может присылать повторный POST раньше, чем закоммитится первая запись в БД).
    Основная защита от дублей — это dedupe_key в БД (см. enqueue_call_webhook); redis лишь
    сокращает окно гонки между параллельными запросами."""
    if not dedupe_key:
        return True
    return bool(redis_client.set(f"communications:dedupe:{dedupe_key}", "1", nx=True, ex=ttl_seconds))
