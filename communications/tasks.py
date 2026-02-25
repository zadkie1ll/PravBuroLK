from typing import Callable, Any

try:
    from celery import shared_task
except Exception:
    # Fallback для проектов без celery: декоратор возвращает функцию с .delay(),
    # которая выполняется синхронно.
    def shared_task(*_args, **_kwargs):  # type: ignore[misc]
        bind = bool(_kwargs.get("bind", False))

        def decorator(func: Callable[..., Any]):
            def delay(*args, **kwargs):
                if bind:
                    return func(None, *args, **kwargs)
                return func(*args, **kwargs)

            setattr(func, "delay", delay)
            return func

        return decorator

from communications.services.call_queue import process_call_event, process_pending_queue


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def process_call_event_task(self, event_id: int) -> None:
    """
    Основная Celery-задача для обработки одного вебхука.

    Что здесь важно понять:
    1) `bind=True` дает доступ к `self` (метаданные задачи, retries и т.д.).
    2) `autoretry_for` + `retry_backoff` включают автоматический retry
       для временных ошибок сети/внешних API.
    3) Бизнес-логика остается в service-слое (`call_queue.py`),
       а задача здесь лишь тонкая обертка для очереди.
    """
    # Важно: пробрасываем исключения наружу, чтобы autoretry реально работал.
    process_call_event(event_id, raise_on_error=True)


@shared_task(bind=True)
def process_pending_queue_task(self, limit: int = 50) -> int:
    """
    Вспомогательная задача: обработать зависшие pending-события пачкой.

    Полезно, если worker какое-то время был выключен, и нужно "догнать"
    очередь из БД.
    """
    return process_pending_queue(limit=limit)
