from .celery_app import celery_app
from .db import SessionLocal
from .services.monitoring import process_all_active_monitors


@celery_app.task(bind=True)
def run_lead_monitoring_task(self) -> dict:
    """Порт lead_control.tasks.run_lead_monitoring_task."""
    db = SessionLocal()
    try:
        return process_all_active_monitors(db)
    finally:
        db.close()
