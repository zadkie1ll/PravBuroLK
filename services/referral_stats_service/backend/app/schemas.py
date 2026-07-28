from pydantic import BaseModel


class ReferralStatRow(BaseModel):
    type: str
    name: str
    ref_link: str
    clicks: int
    applications: int


class ReferralStatsResponse(BaseModel):
    results: list[ReferralStatRow]
    count: int
    page: int
    per_page: int


class DashboardStatsResponse(BaseModel):
    today: int
    week: int
    month: int
    all_time: int
