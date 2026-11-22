from unittest.mock import patch

from fastapi.testclient import TestClient

from app.agent import handle_request
from app.main import app


client = TestClient(app)


VALID_INTENT = {
    "from_station": "北京南",
    "to_station": "上海虹桥",
    "travel_date": "2026-10-25",
    "earliest": "06:00",
    "latest": "12:00",
    "passengers": 1,
    "seat_types": ["二等座"],
    "cheapest_first": True,
    "missing_fields": [],
}


def test_agent_endpoint_exists():
    """确认 /api/agent 已经注册。"""
    with patch("app.agent.parse_with_llm", return_value=VALID_INTENT):
        response = client.post(
            "/api/agent",
            json={
                "request": (
                    "2026年10月25日上午从北京南到上海虹桥，"
                    "1个人，二等座，优先最便宜的"
                )
            },
        )

    assert response.status_code == 200


def test_llm_extracts_complete_intent():
    """模型解析结果应包含完整的结构化行程。"""
    with patch("app.agent.parse_with_llm", return_value=VALID_INTENT):
        result = handle_request(
            "2026年10月25日上午从北京南到上海虹桥，"
            "1个人，二等座，优先最便宜的"
        )

    intent = result["intent"]

    assert intent["from_station"] == "北京南"
    assert intent["to_station"] == "上海虹桥"
    assert intent["travel_date"] == "2026-10-25"
    assert intent["passengers"] == 1
    assert intent["seat_types"] == ["二等座"]
    assert intent["cheapest_first"] is True


def test_missing_information_is_not_guessed():
    """缺少目的地和日期时，Agent不能自行猜测。"""
    incomplete = {
        "from_station": "北京南",
        "to_station": None,
        "travel_date": None,
        "earliest": "00:00",
        "latest": "23:59",
        "passengers": 1,
        "seat_types": ["二等座"],
        "cheapest_first": True,
        "missing_fields": ["to_station", "travel_date"],
    }

    with patch("app.agent.parse_with_llm", return_value=incomplete):
        result = handle_request("从北京南出发，买最便宜的二等座")

    assert result["status"] == "needs_clarification"
    assert "to_station" in result["intent"]["missing_fields"]
    assert "travel_date" in result["intent"]["missing_fields"]
    assert result["trains"] == []


def test_invalid_llm_output_uses_rule_fallback():
    """模型返回非法结果时，应自动切换到规则解析。"""
    with patch(
        "app.agent.parse_with_llm",
        side_effect=ValueError("模型返回了非法JSON"),
    ):
        result = handle_request(
            "2026年10月25日上午从北京南到上海虹桥，二等座"
        )

    assert result["fallback_used"] is True
    assert result["intent"]["from_station"] == "北京南"
    assert result["intent"]["to_station"] == "上海虹桥"


def test_llm_timeout_uses_rule_fallback():
    """模型超时时，基础查询功能仍应可用。"""
    with patch(
        "app.agent.parse_with_llm",
        side_effect=TimeoutError("模型调用超时"),
    ):
        result = handle_request(
            "2026年10月25日上午从北京南到上海虹桥，二等座"
        )

    assert result["fallback_used"] is True
    assert result["status"] in {"ready", "needs_clarification"}


def test_agent_does_not_generate_ticket_prices():
    """意图解析阶段不允许模型生成票价。"""
    malicious_output = {
        **VALID_INTENT,
        "price": 1,
        "minimum_price": 1,
        "payment_url": "https://example.com/pay",
    }

    with patch("app.agent.parse_with_llm", return_value=malicious_output):
        result = handle_request(
            "2026年10月25日从北京南到上海虹桥"
        )

    intent = result["intent"]

    assert "price" not in intent
    assert "minimum_price" not in intent
    assert "payment_url" not in intent