from .celery_app import celery_app
from .db import SessionLocal
from .services import call_processing


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def process_call_event_task(self, event_id: int) -> None:
    """Порт communications.tasks.process_call_event_task из монолита.

    Пробрасываем исключения наружу, чтобы autoretry реально срабатывал —
    бизнес-логика остаётся в call_processing.py, задача лишь тонкая обёртка.
    """
    db = SessionLocal()
    try:
        call_processing.process_call_event(db, event_id, raise_on_error=True)
    finally:
        db.close()


@celery_app.task(bind=True)
def process_pending_queue_task(self, limit: int = 50) -> int:
    """Догоняющая задача: обработать зависшие pending-события пачкой,
    если воркер какое-то время был выключен."""
    db = SessionLocal()
    try:
        return call_processing.process_pending_queue(db, limit=limit)
    finally:
        db.close()
