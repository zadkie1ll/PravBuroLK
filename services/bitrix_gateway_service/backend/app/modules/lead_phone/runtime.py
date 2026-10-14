import asyncio
import logging
import re

from ...services.client import BitrixProfileClient
from .processor import Options
from .queue import Queue

logger = logging.getLogger("lead_phone")


class HideWebhookAccess(logging.Filter):
    def filter(self, record):
        return "/webhooks/bitrix24/" not in record.getMessage()


class Runtime:
    def __init__(self, settings):
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,}", settings.lead_phone_secret):
            raise ValueError("invalid_endpoint_secret")
        webhook = settings.profile_webhook_urls.get(settings.lead_phone_profile)
        if not webhook:
            raise ValueError("unconfigured_profile")
        self.options = Options(
            from_type=settings.lead_phone_from_type, to_type=settings.lead_phone_to_type,
            allowed_sources=frozenset(x.strip() for x in settings.lead_phone_allowed_sources.split(",") if x.strip()),
            dry_run=settings.lead_phone_dry_run, max_attempts=settings.lead_phone_max_attempts,
            retry_seconds=settings.lead_phone_retry_seconds,
        )
        self.options.validate()
        self.queue = Queue(
            settings.lead_phone_queue_path, self.options,
            settings.lead_contact_phone_field, settings.lead_contact_stage_id,
        )
        self.client = BitrixProfileClient(webhook)
        self.stopping = asyncio.Event()
        self.task = None
        self.available = False

    async def start(self):
        await asyncio.to_thread(self.queue.open)
        self.available = True
        self.task = asyncio.create_task(self.run())

    async def run(self):
        while not self.stopping.is_set():
            try:
                await asyncio.to_thread(self.queue.tick, self.client.call)
                self.available = True
            except Exception:
                self.available = False
                logger.error("lead_phone queue_unavailable")
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=1)
            except TimeoutError:
                pass

    async def stop(self):
        self.stopping.set()
        if self.task:
            await self.task
        self.queue.close()
