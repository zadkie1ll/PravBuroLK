from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone

from call_queue.models import (
    BitrixSyncLog,
    CallAttempt,
    CallEntityType,
    CallQueueItem,
    CallQueueItemStatus,
    CallResult,
    CallSession,
    CallSessionStatus,
)
from call_queue.services.bitrix.deal_service import BitrixDealService
from call_queue.services.bitrix.timeline_service import BitrixTimelineService

User = get_user_model()

REQUEUEABLE_STATUSES = (
    CallQueueItemStatus.NEW,
    CallQueueItemStatus.POSTPONED,
    CallQueueItemStatus.SKIPPED,
    CallQueueItemStatus.FAILED,
)


class QueueService:
    stale_lock_minutes = 30

    def __init__(
        self,
        deal_service: BitrixDealService | None = None,
        timeline_service: BitrixTimelineService | None = None,
    ):
        self.deal_service = deal_service or BitrixDealService()
        self.timeline_service = timeline_service or BitrixTimelineService()

    def create_session_with_queue(self, *, manager: User, filters: dict, activate: bool = False) -> CallSession:
        session = CallSession.objects.create(
            created_by=manager,
            entity_type=filters.get("entity_type", CallEntityType.DEAL),
            date_from=filters["date_from"],
            date_to=filters["date_to"],
            filters_json={
                "entity_type": filters.get("entity_type", CallEntityType.DEAL),
                "date_from": filters["date_from"].isoformat(),
                "date_to": filters["date_to"].isoformat(),
                "stage_id": filters.get("stage_id", ""),
                "source_id": filters.get("source_id", ""),
                "responsible_id": filters.get("responsible_id", ""),
                "only_unanswered": bool(filters.get("only_unanswered")),
                "only_without_repeat": bool(filters.get("only_without_repeat")),
            },
            status=CallSessionStatus.ACTIVE if activate else CallSessionStatus.DRAFT,
        )
        deals = self.deal_service.fetch_deals(session.filters_json)
        self.populate_session_queue(session, deals)
        if activate and session.total_items == 0:
            session.status = CallSessionStatus.COMPLETED
            session.save(update_fields=["status", "updated_at"])
        return session

    def populate_session_queue(self, session: CallSession, deals: Iterable[dict]) -> int:
        created_count = 0
        for deal in deals:
            _, created = CallQueueItem.objects.get_or_create(
                session=session,
                entity_type=deal.get("entity_type", session.entity_type),
                bitrix_entity_id=deal["bitrix_entity_id"],
                defaults={
                    "bitrix_contact_id": deal.get("bitrix_contact_id"),
                    "client_name": deal.get("client_name", ""),
                    "phone": deal.get("phone", ""),
                    "lead_created_at": deal.get("lead_created_at"),
                    "source_id": deal.get("source_id", ""),
                    "source_name": deal.get("source_name", ""),
                    "stage_id": deal.get("stage_id", ""),
                    "stage_name": deal.get("stage_name", ""),
                    "responsible_id": deal.get("responsible_id", ""),
                    "responsible_name": deal.get("responsible_name", ""),
                    "bitrix_url": deal.get("bitrix_url", ""),
                    "last_call_result": deal.get("last_call_result", ""),
                    "repeat_unanswered": bool(deal.get("repeat_unanswered")),
                },
            )
            created_count += int(created)
        self.refresh_session_counters(session)
        return created_count

    def refresh_session_counters(self, session: CallSession) -> CallSession:
        counters = session.items.aggregate(
            total_items=Count("id"),
            processed_items=Count("id", filter=Q(status=CallQueueItemStatus.DONE)),
            success_count=Count("id", filter=Q(status=CallQueueItemStatus.DONE)),
            failed_count=Count("id", filter=Q(status=CallQueueItemStatus.FAILED)),
            remaining_items=Count(
                "id",
                filter=Q(
                    status__in=[
                        CallQueueItemStatus.NEW,
                        CallQueueItemStatus.IN_PROGRESS,
                        CallQueueItemStatus.POSTPONED,
                        CallQueueItemStatus.SKIPPED,
                        CallQueueItemStatus.FAILED,
                    ]
                ),
            ),
        )
        session.total_items = counters["total_items"] or 0
        session.processed_items = counters["processed_items"] or 0
        session.success_count = counters["success_count"] or 0
        session.failed_count = counters["failed_count"] or 0
        if session.total_items and (counters["remaining_items"] or 0) == 0:
            session.status = CallSessionStatus.COMPLETED
        elif session.total_items and session.status == CallSessionStatus.DRAFT:
            session.status = CallSessionStatus.ACTIVE
        session.save(
            update_fields=[
                "total_items",
                "processed_items",
                "success_count",
                "failed_count",
                "status",
                "updated_at",
            ]
        )
        return session

    def get_next_item_for_manager(self, session: CallSession, manager: User) -> CallQueueItem | None:
        now = timezone.now()
        stale_before = now - timedelta(minutes=self.stale_lock_minutes)
        with transaction.atomic():
            (
                CallQueueItem.objects.select_for_update(skip_locked=True)
                .filter(
                    session=session,
                    status=CallQueueItemStatus.IN_PROGRESS,
                    locked_at__lte=stale_before,
                )
                .update(
                    status=CallQueueItemStatus.NEW,
                    assigned_to=None,
                    locked_at=None,
                )
            )

            current_item = (
                CallQueueItem.objects.select_for_update(skip_locked=True)
                .filter(
                    session=session,
                    assigned_to=manager,
                    status=CallQueueItemStatus.IN_PROGRESS,
                )
                .order_by("locked_at", "id")
                .first()
            )
            if current_item:
                return current_item

            item = (
                CallQueueItem.objects.select_for_update(skip_locked=True)
                .filter(session=session)
                .filter(
                    Q(status__in=REQUEUEABLE_STATUSES)
                    | Q(
                        status=CallQueueItemStatus.IN_PROGRESS,
                        locked_at__lte=stale_before,
                    )
                )
                .annotate(
                    priority=Case(
                        When(status=CallQueueItemStatus.NEW, then=Value(0)),
                        When(status=CallQueueItemStatus.POSTPONED, then=Value(1)),
                        When(status=CallQueueItemStatus.SKIPPED, then=Value(2)),
                        When(status=CallQueueItemStatus.FAILED, then=Value(3)),
                        default=Value(4),
                        output_field=IntegerField(),
                    )
                )
                .order_by("priority", "attempts_count", "lead_created_at", "id")
                .first()
            )
            if not item:
                self.refresh_session_counters(session)
                return None

            item.status = CallQueueItemStatus.IN_PROGRESS
            item.assigned_to = manager
            item.locked_at = now
            item.save(update_fields=["status", "assigned_to", "locked_at", "updated_at"])
            return item

    def process_call_result(
        self,
        *,
        queue_item: CallQueueItem,
        manager: User,
        result: str,
        comment: str = "",
        provider_call_id: str = "",
    ) -> dict:
        now = timezone.now()
        with transaction.atomic():
            locked_item = CallQueueItem.objects.select_for_update().select_related("session").get(pk=queue_item.pk)
            if locked_item.assigned_to_id and locked_item.assigned_to_id != manager.id:
                raise ValueError("Элемент очереди уже назначен другому менеджеру.")

            attempt = CallAttempt.objects.create(
                queue_item=locked_item,
                manager=manager,
                started_at=locked_item.locked_at or now,
                finished_at=now,
                result=result,
                comment=comment,
                provider_call_id=provider_call_id or locked_item.last_provider_call_id,
            )

            locked_item.attempts_count += 1
            locked_item.last_call_result = result
            locked_item.last_call_at = now
            locked_item.assigned_to = None
            locked_item.locked_at = None

            if result == CallResult.SUCCESS:
                locked_item.status = CallQueueItemStatus.DONE
                locked_item.needs_manual_processing = True
            elif result == CallResult.POSTPONED:
                locked_item.status = CallQueueItemStatus.POSTPONED
            elif result == CallResult.SKIPPED:
                locked_item.status = CallQueueItemStatus.SKIPPED
            else:
                locked_item.status = CallQueueItemStatus.FAILED

            locked_item.repeat_unanswered = locked_item.attempts_count > 1 and result in {
                CallResult.NO_ANSWER,
                CallResult.BUSY,
                CallResult.UNAVAILABLE,
            }
            locked_item.save(
                update_fields=[
                    "attempts_count",
                    "last_call_result",
                    "last_call_at",
                    "assigned_to",
                    "locked_at",
                    "status",
                    "needs_manual_processing",
                    "repeat_unanswered",
                    "updated_at",
                ]
            )
            self.refresh_session_counters(locked_item.session)

        sync_error = self.sync_result_to_bitrix(locked_item, attempt)
        return {"attempt": attempt, "queue_item": locked_item, "sync_error": sync_error}

    def sync_result_to_bitrix(self, queue_item: CallQueueItem, attempt: CallAttempt) -> str:
        comment = self.build_timeline_comment(queue_item, attempt)
        try:
            update_response = self.deal_service.update_entity_after_call(
                queue_item.entity_type,
                queue_item.bitrix_entity_id,
                attempt.result,
                queue_item.repeat_unanswered,
            )
            BitrixSyncLog.objects.create(
                entity_type=queue_item.entity_type,
                entity_id=str(queue_item.bitrix_entity_id),
                action="update_deal_after_call",
                request_payload={
                    "result": attempt.result,
                    "repeat_unanswered": queue_item.repeat_unanswered,
                },
                response_payload=update_response if isinstance(update_response, dict) else {"result": update_response},
                success=True,
            )

            timeline_response = self.timeline_service.add_comment(
                queue_item.entity_type,
                queue_item.bitrix_entity_id,
                comment,
            )
            BitrixSyncLog.objects.create(
                entity_type=queue_item.entity_type,
                entity_id=str(queue_item.bitrix_entity_id),
                action="timeline_comment_add",
                request_payload={"comment": comment},
                response_payload=timeline_response if isinstance(timeline_response, dict) else {"result": timeline_response},
                success=True,
            )
            return ""
        except Exception as exc:
            BitrixSyncLog.objects.create(
                entity_type=queue_item.entity_type,
                entity_id=str(queue_item.bitrix_entity_id),
                action="sync_call_result",
                request_payload={
                    "result": attempt.result,
                    "comment": comment,
                    "repeat_unanswered": queue_item.repeat_unanswered,
                },
                response_payload={},
                success=False,
                error_text=str(exc),
            )
            return str(exc)

    def build_timeline_comment(self, queue_item: CallQueueItem, attempt: CallAttempt) -> str:
        labels = {
            CallResult.NO_ANSWER: "не ответил",
            CallResult.BUSY: "занято",
            CallResult.UNAVAILABLE: "недоступен",
            CallResult.SUCCESS: "успешный контакт",
            CallResult.POSTPONED: "перезвонить позже",
            CallResult.SKIPPED: "пропущен",
        }
        text = f"Автообзвон #{queue_item.attempts_count} — {labels.get(attempt.result, attempt.result)}"
        if attempt.comment:
            text = f"{text}. Комментарий: {attempt.comment}"
        return text
