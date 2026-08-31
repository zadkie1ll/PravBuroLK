from pydantic import BaseModel


class SourceStat(BaseModel):
    source: str
    clicks: int


class DestinationStat(BaseModel):
    destination: str
    sources: list[SourceStat]
    total_clicks: int


class StatsResponse(BaseModel):
    stats: list[DestinationStat]


class CreateSourcePayload(BaseModel):
    source: str
    destination: str


class UpdateSourcePayload(BaseModel):
    new_source: str
    new_destination: str


class UpdateDestinationPayload(BaseModel):
    old_destination: str
    new_destination: str


class DeleteDestinationPayload(BaseModel):
    destination: str


class MutationResponse(BaseModel):
    success: bool
    message: str


# --- Новая система разметки ---

class DictionaryItem(BaseModel):
    id: int
    code: str
    is_active: bool


class BotBlockItem(BaseModel):
    id: int
    key: str
    title: str
    is_active: bool


class DictionariesResponse(BaseModel):
    utm_sources: list[DictionaryItem]
    utm_mediums: list[DictionaryItem]
    bot_blocks: list[BotBlockItem]


class AddDictionaryValuePayload(BaseModel):
    code: str


class AddBotBlockPayload(BaseModel):
    key: str
    title: str


class CreateMarketingLinkPayload(BaseModel):
    link_type: str
    destination: str | None = None
    utm_source_id: int
    utm_medium_id: int
    utm_campaign: str
    utm_content: str = ""
    utm_term: str = ""
    bot_block_id: int | None = None


class MarketingLinkOut(BaseModel):
    id: int
    source: str
    link_type: str
    destination: str
    utm_source: str
    utm_medium: str
    utm_campaign: str
    utm_content: str
    utm_term: str
    bot_block: str | None = None
    public_link: str


class CreateMarketingLinkResponse(BaseModel):
    link: MarketingLinkOut
    is_existing: bool


class MarketingStatsRow(BaseModel):
    group_value: str
    clicks: int


class MarketingStatsResponse(BaseModel):
    rows: list[MarketingStatsRow]
    total_clicks: int
    page: int
    total_pages: int
    total_rows: int


class KnownValuesResponse(BaseModel):
    campaigns: list[str]
    contents: list[str]
    terms: list[str]
