from pydantic import BaseModel, Field


class TravelIntent(BaseModel):
    from_station: str | None = None
    to_station: str | None = None
    travel_date: str | None = None
    earliest: str = "00:00"
    latest: str = "23:59"
    passengers: int = Field(default=1, ge=1, le=9)
    seat_types: list[str] = []
    train_types: list[str] = []
    cheapest_first: bool = True
    missing_fields: list[str] = []