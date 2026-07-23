from pydantic import BaseModel


class WebhookAcceptedResponse(BaseModel):
    success: bool
    event_id: int
    status: str
    queued: bool


class ManualAnalyzeResponse(BaseModel):
    status: str
    event_id: int
    call_id: str
    message: str | None = None
    lead_id: str | None = None
    deal_id: str | None = None
    contact_id: str | None = None
    analyzed_at: str | None = None
    summary: str | None = None
