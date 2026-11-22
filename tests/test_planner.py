from datetime import date

from app.planner import parse_request, score_train
from app.railway import RailwayClient


def test_parse_natural_request():
    result = parse_request("明天上午从北京南到上海虹桥，2人，优先二等座", today=date(2026, 10, 24))
    assert result["from_station"] == "北京南"
    assert result["to_station"] == "上海虹桥"
    assert result["travel_date"] == "2026-10-25"
    assert result["earliest"] == "06:00"
    assert result["latest"] == "12:00"
    assert result["passengers"] == 2
    assert result["seat_types"] == ["二等座"]
    assert result["understood"] is True


def test_missing_fields_are_reported():
    result = parse_request("帮我买一张二等座", today=date(2026, 10, 24))
    assert result["understood"] is False
    assert "出发地" in result["missing"]
    assert "出发日期" in result["missing"]


def test_available_preferred_seat_scores_higher():
    request = {"seat_types": ["二等座"], "earliest": "06:00", "latest": "12:00"}
    available = {"seats": {"二等座": "5"}, "duration_minutes": 180, "start_time": "08:00", "bookable": True}
    unavailable = {"seats": {"二等座": "无"}, "duration_minutes": 180, "start_time": "08:00", "bookable": True}
    assert score_train(available, request)[0] > score_train(unavailable, request)[0]


def test_price_parser_accepts_yuan_symbol():
    assert RailwayClient._parse_price("¥553.0") == 553.0
    assert RailwayClient._parse_price("--") is None

