from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent import handle_request
from .models import (
    AgentRequest,
    BookingLinkRequest,
    PlanRequest,
    PreferenceRequest,
    PriceRequest,
    SearchRequest,
)
from .planner import parse_request
from .railway import railway



ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PREFERENCES = ROOT / "data" / "preferences.json"
app = FastAPI(title="铁路出行助手", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "铁路出行助手", "purchase_mode": "official-confirmation-required"}


@app.post("/api/plan")
def plan(request: PlanRequest) -> dict[str, Any]:
    try:
        return parse_request(request.request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/search")
def search(request: SearchRequest) -> dict[str, Any]:
    try:
        return railway.search(request.model_dump())
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400 if isinstance(exc, ValueError) else 503, detail=str(exc)) from exc


@app.post("/api/prices")
def prices(request: PriceRequest) -> dict[str, Any]:
    return railway.prices(request.travel_date, [train.model_dump() for train in request.trains], request.preferred_seats)


@app.post("/api/booking-link")
def booking_link(request: BookingLinkRequest) -> dict[str, str]:
    try:
        return {
            "url": railway.booking_url(request.from_station, request.to_station, request.travel_date),
            "notice": "请仅在中国铁路12306官方网站完成登录、乘客确认、订单提交和支付。",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/preferences")
def get_preferences() -> dict[str, Any]:
    if not PREFERENCES.exists():
        return PreferenceRequest().model_dump()
    return json.loads(PREFERENCES.read_text(encoding="utf-8"))


@app.post("/api/preferences")
def save_preferences(request: PreferenceRequest) -> dict[str, Any]:
    PREFERENCES.parent.mkdir(parents=True, exist_ok=True)
    PREFERENCES.write_text(
        json.dumps(request.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"saved": True, **request.model_dump()}

@app.post("/api/agent")
def run_agent(request: AgentRequest):
    return handle_request(request.request)

