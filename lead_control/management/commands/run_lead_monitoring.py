from django.core.management.base import BaseCommand

from lead_control.services import process_all_active_monitors


class Command(BaseCommand):
    help = "Runs lead monitoring service"

    def handle(self, *args, **options):
        stats = process_all_active_monitors()
        self.stdout.write(self.style.SUCCESS(str(stats)))