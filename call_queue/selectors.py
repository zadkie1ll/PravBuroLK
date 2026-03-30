from django.db.models import Count, Q

from .models import CallQueueItem, CallQueueItemStatus, CallSession


def get_active_item_for_manager(session: CallSession, manager) -> CallQueueItem | None:
    return (
        session.items.select_related("assigned_to")
        .prefetch_related("attempts__manager")
        .filter(
            assigned_to=manager,
            status=CallQueueItemStatus.IN_PROGRESS,
        )
        .order_by("locked_at", "id")
        .first()
    )


def get_session_with_stats(session_id: int) -> CallSession:
    return (
        CallSession.objects.annotate(
            remaining_count=Count(
                "items",
                filter=Q(
                    items__status__in=[
                        CallQueueItemStatus.NEW,
                        CallQueueItemStatus.IN_PROGRESS,
                        CallQueueItemStatus.POSTPONED,
                        CallQueueItemStatus.SKIPPED,
                        CallQueueItemStatus.FAILED,
                    ]
                ),
                distinct=True,
            ),
        )
        .select_related("created_by")
        .get(pk=session_id)
    )


def get_recent_sessions(limit: int = 10):
    return CallSession.objects.select_related("created_by").order_by("-created_at")[:limit]
