from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any


SEATS = ("商务座", "特等座", "一等座", "二等座", "软卧", "硬卧", "软座", "硬座", "无座")
TIME_WORDS = {
    "凌晨": ("00:00", "06:00"),
    "早上": ("05:00", "09:00"),
    "上午": ("06:00", "12:00"),
    "中午": ("11:00", "14:00"),
    "下午": ("12:00", "18:00"),
    "晚上": ("18:00", "23:59"),
}


def _date_from_text(text: str, today: date | None = None) -> str | None:
    today = today or date.today()
    if "后天" in text:
        return (today + timedelta(days=2)).isoformat()
    if "明天" in text:
        return (today + timedelta(days=1)).isoformat()
    if "今天" in text:
        return today.isoformat()
    full = re.search(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})日?", text)
    if full:
        return date(int(full.group(1)), int(full.group(2)), int(full.group(3))).isoformat()
    short = re.search(r"(?<!\d)(\d{1,2})月(\d{1,2})日?", text)
    if short:
        candidate = date(today.year, int(short.group(1)), int(short.group(2)))
        if candidate < today:
            candidate = candidate.replace(year=today.year + 1)
        return candidate.isoformat()
    return None


def parse_request(text: str, today: date | None = None) -> dict[str, Any]:
    clean = " ".join(text.strip().split())
    route = re.search(r"从\s*([^，,。\s]+?)\s*(?:到|去|前往)\s*([^，,。\s]+)", clean)
    if not route:
        route = re.search(r"([^，,。\s]+?)\s*(?:到|去)\s*([^，,。\s]+).*?(?:票|车)", clean)
    travel_date = _date_from_text(clean, today)
    earliest, latest = "00:00", "23:59"
    for word, window in TIME_WORDS.items():
        if word in clean:
            earliest, latest = window
            break
    explicit = re.search(r"(\d{1,2}):?(\d{2})?\s*(?:到|至|-)\s*(\d{1,2}):?(\d{2})?", clean)
    if explicit:
        earliest = f"{int(explicit.group(1)):02d}:{int(explicit.group(2) or 0):02d}"
        latest = f"{int(explicit.group(3)):02d}:{int(explicit.group(4) or 0):02d}"
    seats = [seat for seat in SEATS if seat in clean]
    train_types = []
    for label, code in (("高铁", "G"), ("动车", "D"), ("城际", "C"), ("直达", "Z"), ("特快", "T"), ("快速", "K")):
        if label in clean:
            train_types.append(code)
    people = re.search(r"(\d+)\s*(?:人|张)", clean)
    missing = []
    if not route:
        missing.extend(["出发地", "目的地"])
    if not travel_date:
        missing.append("出发日期")
    return {
        "from_station": route.group(1) if route else "",
        "to_station": route.group(2) if route else "",
        "travel_date": travel_date or "",
        "earliest": earliest,
        "latest": latest,
        "train_types": train_types,
        "seat_types": seats or ["二等座", "一等座", "硬座", "硬卧"],
        "passengers": int(people.group(1)) if people else 1,
        "direct_only": True,
        "missing": missing,
        "understood": not missing,
    }


def score_train(train: dict[str, Any], request: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    seats = train.get("seats", {})
    preferred = request.get("seat_types", [])
    available = [seat for seat in preferred if seats.get(seat) not in (None, "", "无", "--", "候补")]
    if available:
        score += 55
        reasons.append(f"{available[0]}有余票")
    elif any(value not in (None, "", "无", "--") for value in seats.values()):
        score += 20
        reasons.append("其他席别可能有票")
    duration = train.get("duration_minutes", 9999)
    score += max(0, 25 - duration // 30)
    if duration <= 240:
        reasons.append("行程时间较短")
    start = train.get("start_time", "23:59")
    if request.get("earliest", "00:00") <= start <= request.get("latest", "23:59"):
        score += 15
        reasons.append("符合出发时段")
    if train.get("bookable"):
        score += 5
    return score, reasons

