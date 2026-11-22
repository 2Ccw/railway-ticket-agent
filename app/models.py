from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    from_station: str
    to_station: str
    travel_date: str
    earliest: str = "00:00"
    latest: str = "23:59"
    train_types: list[str] = Field(default_factory=list)
    seat_types: list[str] = Field(default_factory=lambda: ["二等座", "一等座", "硬座", "硬卧"])
    passengers: int = Field(default=1, ge=1, le=9)
    direct_only: bool = True


class PlanRequest(BaseModel):
    request: str


class PreferenceRequest(BaseModel):
    home_station: str = ""
    preferred_seats: list[str] = Field(default_factory=list)
    earliest: str = "06:00"
    latest: str = "22:00"


class BookingLinkRequest(BaseModel):
    from_station: str
    to_station: str
    travel_date: str


class PriceTrain(BaseModel):
    train_no: str
    train_code: str
    from_station_no: str
    to_station_no: str
    seat_types: str
    seats: dict[str, str] = Field(default_factory=dict)


class PriceRequest(BaseModel):
    travel_date: str
    preferred_seats: list[str] = Field(default_factory=list)
    trains: list[PriceTrain] = Field(min_length=1, max_length=40)

class AgentRequest(BaseModel):
    request: str

