from __future__ import annotations

import json
import logging
from datetime import date

from .llm_client import MODEL, client
from .planner import parse_request
from .prompts import SYSTEM_PROMPT
from .schemas import TravelIntent
from .trajectory import record_trajectory

logger = logging.getLogger(__name__)


def parse_with_llm(text: str) -> dict:
    user_prompt = f"""
当前日期：{date.today().isoformat()}

请把用户的铁路出行需求解析成JSON。

用户输入：
{text}

只返回JSON，字段必须是：
{{
  "from_station": "出发站或null",
  "to_station": "到达站或null",
  "travel_date": "YYYY-MM-DD或null",
  "earliest": "HH:MM",
  "latest": "HH:MM",
  "passengers": 1,
  "seat_types": ["二等座"],
  "cheapest_first": true,
  "missing_fields": []
}}

规则：
1. “今天、明天、后天”根据当前日期计算。
2. 用户要求最便宜时，cheapest_first设为true。
3. 不知道的信息必须设为null并写入missing_fields。
4. 不得生成票价、余票、支付链接或订单结果。
5. 只能输出JSON，不要输出Markdown。
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0,
            max_tokens=500,
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("模型返回内容为空")

        # 兼容少数模型返回Markdown代码块的情况
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json")
            cleaned = cleaned.removeprefix("```")
            cleaned = cleaned.removesuffix("```").strip()

        raw_intent = json.loads(cleaned)

        # 校验并删除模型添加的未知字段
        intent = TravelIntent.model_validate(raw_intent)
        return intent.model_dump()

    except Exception as exc:
        logger.warning("大模型解析失败，将使用规则解析：%s", exc)
        raise RuntimeError("大模型解析失败") from exc


def handle_request(text: str) -> dict:
    fallback_used = False

    try:
        raw_intent = parse_with_llm(text)
    except (ValueError, RuntimeError, TimeoutError):
        raw_intent = parse_request(text)
        raw_intent["missing_fields"] = raw_intent.get("missing", [])
        fallback_used = True

    intent = TravelIntent.model_validate(raw_intent)
    intent_data = intent.model_dump()
    missing = intent_data["missing_fields"]

    result  = {
        "status": "needs_clarification" if missing else "ready",
        "message": (
            "请补充：" + "、".join(missing)
            if missing
            else "行程解析完成"
        ),
        "intent": intent_data,
        "trains": [],
        "fallback_used": fallback_used,
    }
    record_trajectory({
        "task": text,
        "verdict": "passed" if result["status"] == "ready" else "failed",
        "steps": [
            {
                "action": "parse_travel_intent",
                "summary": (
                    "LLM调用成功，结构化意图解析完成"
                    if not fallback_used
                    else "LLM调用失败，使用规则解析回退"
                ),
            },
            {
                "action": "validate_travel_intent",
                "summary": "使用Pydantic完成结构化参数校验",
            },
        ],
        "final": result["message"],
        "fallback_used": fallback_used,
        "intent": intent_data,
    })

    return result