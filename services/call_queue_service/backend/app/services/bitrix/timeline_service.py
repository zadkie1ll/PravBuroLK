from __future__ import annotations

from .client import BitrixClient


class BitrixTimelineService:
    def __init__(self, client: BitrixClient | None = None):
        self.client = client or BitrixClient()

    def add_comment(self, entity_type: str, entity_id: int, comment: str):
        return self.client.call(
            "crm.timeline.comment.add",
            {
                "fields": {
                    "ENTITY_ID": int(entity_id),
                    "ENTITY_TYPE": entity_type,
                    "COMMENT": comment,
                }
            },
        )
