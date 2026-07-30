from celery import Celery
from celery.schedules import crontab

from .config import settings

celery_app = Celery(
    "lead_control",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        # Порт pravburo/settings.py: CELERY_BEAT_SCHEDULE["lead-control-working-hours-monitoring"]
        "lead-control-working-hours-monitoring": {
            "task": "app.tasks.run_lead_monitoring_task",
            "schedule": crontab(minute=0, hour="10,13,16,19"),
        },
    },
)
