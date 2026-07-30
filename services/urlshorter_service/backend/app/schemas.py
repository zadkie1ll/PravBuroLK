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
