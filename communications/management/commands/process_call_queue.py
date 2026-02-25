from django.conf import settings
from django.core.management.base import BaseCommand

from communications.services.call_queue import process_pending_queue


class Command(BaseCommand):
    help = "Process pending call webhook events (sync by default, Celery optional)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum number of pending events to process",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if getattr(settings, "COMMUNICATIONS_USE_CELERY", False):
            try:
                from communications.tasks import process_pending_queue_task

                task = process_pending_queue_task.delay(limit=limit)
                self.stdout.write(self.style.SUCCESS(f"Task queued: {task.id}"))
                return
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(f"Celery unavailable, fallback to sync mode: {exc}")
                )

        processed = process_pending_queue(limit=limit)
        self.stdout.write(self.style.SUCCESS(f"Processed: {processed}"))
