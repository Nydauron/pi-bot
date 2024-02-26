from datetime import datetime

from beanie import Document
from pydantic import BaseModel, Field


class SiteHTTPResult(BaseModel):
    url: str
    status_code: int


class SiteStatusResult(Document):
    domain: str
    dt: datetime
    ping: float | None
    http: SiteHTTPResult | None


class AggregateStatus(BaseModel):
    ping: float | None
    http: SiteHTTPResult | None
    recordedAt: datetime


class AggregateStatusList(BaseModel):
    domain: str = Field(None, alias="_id")
    results: list[AggregateStatus]
