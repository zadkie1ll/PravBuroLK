from typing import Any, Callable

try:
    from celery import shared_task
except Exception:
    # Fallback для окружений без celery: задача может быть вызвана напрямую через .delay().
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

from lead_control.services import process_all_active_monitors


@shared_task(bind=True)
def run_lead_monitoring_task(self) -> dict:
    return process_all_active_monitors()
