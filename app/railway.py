from __future__ import annotations

import json
import re
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from .planner import score_train


BASE = "https://kyfw.12306.cn"
ROOT = Path(__file__).resolve().parents[1]
FALLBACK_STATIONS = {
    "北京": "BJP", "北京北": "VAP", "北京南": "VNP", "北京西": "BXP",
    "上海": "SHH", "上海虹桥": "AOH", "上海南": "SNH",
    "广州": "GZQ", "广州南": "IZQ", "深圳": "SZQ", "深圳北": "IOQ",
    "杭州": "HZH", "杭州东": "HGH", "南京": "NJH", "南京南": "NKH",
    "成都": "CDW", "成都东": "ICW", "重庆北": "CUW", "重庆西": "CXW",
    "武汉": "WHN", "西安": "XAY", "西安北": "EAY", "郑州": "ZZF",
    "郑州东": "ZAF", "长沙南": "CWQ", "天津": "TJP", "天津西": "TXP",
}
SEAT_INDEXES = {
    "商务座": 32, "特等座": 25, "一等座": 31, "二等座": 30,
    "高级软卧": 21, "软卧": 23, "动卧": 33, "硬卧": 28,
    "软座": 24, "硬座": 29, "无座": 26, "其他": 22,
}
PRICE_CODES = {
    "商务座": "A9", "特等座": "P", "一等座": "M", "二等座": "O",
    "高级软卧": "A6", "软卧": "A4", "动卧": "F", "硬卧": "A3",
    "软座": "A2", "硬座": "A1", "无座": "WZ",
}
UNAVAILABLE = {None, "", "无", "--", "候补"}


class RailwayClient:
    def __init__(self) -> None:
        self.client = httpx.Client(
            base_url=BASE,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
                "Referer": f"{BASE}/otn/leftTicket/init",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=15,
            follow_redirects=True,
        )
        self._stations: dict[str, str] | None = None
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._price_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._last_request = 0.0

    def stations(self) -> dict[str, str]:
        if self._stations is not None:
            return self._stations
        stations = dict(FALLBACK_STATIONS)
        try:
            response = self.client.get("/otn/resources/js/framework/station_name.js")
            response.raise_for_status()
            for name, code in re.findall(r"\|([^|]+)\|([A-Z]+)\|", response.text):
                stations[name] = code
        except httpx.HTTPError:
            pass
        self._stations = stations
        return stations

    def resolve_station(self, name: str) -> tuple[str, str]:
        clean = name.strip().removesuffix("站")
        stations = self.stations()
        if clean in stations:
            return clean, stations[clean]
        matches = [(station, code) for station, code in stations.items() if clean in station]
        if len(matches) == 1:
            return matches[0]
        suggestions = [station for station, _ in matches[:8]]
        raise ValueError(f"无法唯一识别车站“{name}”" + (f"，可能是：{', '.join(suggestions)}" if suggestions else ""))

    def _rate_limit(self, interval: float = 1.5) -> None:
        with self._lock:
            wait = interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    @staticmethod
    def _minutes(value: str) -> int:
        match = re.match(r"(?:(\d+):)?(\d+)", value or "")
        if not match:
            return 9999
        hours = int(match.group(1) or 0)
        return hours * 60 + int(match.group(2))

    def search(self, request: dict[str, Any]) -> dict[str, Any]:
        travel_date = date.fromisoformat(request["travel_date"])
        if travel_date < date.today():
            raise ValueError("出发日期不能早于今天")
        if travel_date > date.today() + timedelta(days=30):
            raise ValueError("查询日期超出当前预售期，请稍后再查")
        from_name, from_code = self.resolve_station(request["from_station"])
        to_name, to_code = self.resolve_station(request["to_station"])
        cache_key = json.dumps([request, from_code, to_code], ensure_ascii=False, sort_keys=True)
        cached = self._cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < 30:
            return {**cached[1], "cached": True}
        self._rate_limit()
        try:
            self.client.get("/otn/leftTicket/init")
            response = self.client.get(
                "/otn/leftTicket/queryG",
                params={
                    "leftTicketDTO.train_date": request["travel_date"],
                    "leftTicketDTO.from_station": from_code,
                    "leftTicketDTO.to_station": to_code,
                    "purpose_codes": "ADULT",
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError("12306官方查询服务暂时不可用，请稍后重试或在官方App查询") from exc
        rows = payload.get("data", {}).get("result", [])
        trains = []
        for raw in rows:
            fields = raw.split("|")
            if len(fields) < 34:
                continue
            code = fields[3]
            if request.get("train_types") and not any(code.startswith(prefix) for prefix in request["train_types"]):
                continue
            start_time = fields[8]
            if not request.get("earliest", "00:00") <= start_time <= request.get("latest", "23:59"):
                continue
            seats = {name: fields[index] if index < len(fields) else "" for name, index in SEAT_INDEXES.items()}
            train = {
                "train_code": code,
                "train_no": fields[2],
                "from_station_no": fields[16],
                "to_station_no": fields[17],
                "seat_types": fields[35] if len(fields) > 35 else "",
                "from_station": from_name,
                "to_station": to_name,
                "start_time": start_time,
                "arrive_time": fields[9],
                "duration": fields[10],
                "duration_minutes": self._minutes(fields[10]),
                "bookable": fields[11] == "Y",
                "seats": seats,
            }
            train["score"], train["reasons"] = score_train(train, request)
            trains.append(train)
        trains.sort(key=lambda item: (-item["score"], item["duration_minutes"], item["start_time"]))
        result = {
            "query": {**request, "from_station": from_name, "to_station": to_name},
            "trains": trains,
            "count": len(trains),
            "queried_at": datetime.now().isoformat(timespec="seconds"),
            "source": "中国铁路12306官方查询服务",
            "cached": False,
        }
        self._cache[cache_key] = (time.monotonic(), result)
        return result

    @staticmethod
    def _parse_price(value: Any) -> float | None:
        if not isinstance(value, str):
            return None
        match = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
        return float(match.group()) if match else None

    def prices(self, travel_date: str, trains: list[dict[str, Any]], preferred_seats: list[str]) -> dict[str, Any]:
        results = []
        for train in trains:
            cache_key = "|".join((travel_date, train["train_no"], train["from_station_no"], train["to_station_no"]))
            cached = self._price_cache.get(cache_key)
            if cached and time.monotonic() - cached[0] < 300:
                payload = cached[1]
            else:
                self._rate_limit(0.3)
                try:
                    response = self.client.get("/otn/leftTicket/queryTicketPrice", params={
                        "train_no": train["train_no"], "from_station_no": train["from_station_no"],
                        "to_station_no": train["to_station_no"], "seat_types": train["seat_types"],
                        "train_date": travel_date,
                    })
                    response.raise_for_status()
                    payload = response.json().get("data", {})
                except (httpx.HTTPError, ValueError):
                    payload = {}
                self._price_cache[cache_key] = (time.monotonic(), payload)
            seat_prices = {seat: price for seat, code in PRICE_CODES.items() if (price := self._parse_price(payload.get(code))) is not None}
            available = {seat: price for seat, price in seat_prices.items() if train.get("seats", {}).get(seat) not in UNAVAILABLE}
            available.pop("无座",None)
            preferred_available = {seat: price for seat, price in available.items() if seat in preferred_seats}
            candidates = preferred_available or available
            cheapest_seat = min(candidates, key=candidates.get) if candidates else None
            results.append({"train_no": train["train_no"], "train_code": train["train_code"], "prices": seat_prices,
                            "minimum_price": candidates.get(cheapest_seat) if cheapest_seat else None,
                            "cheapest_seat": cheapest_seat, "preferred_price": bool(preferred_available)})
        return {"trains": results, "currency": "CNY", "source": "中国铁路12306官方票价服务"}

    def booking_url(self, from_station: str, to_station: str, travel_date: str) -> str:
        from_name, from_code = self.resolve_station(from_station)
        to_name, to_code = self.resolve_station(to_station)
        fs = quote(f"{from_name},{from_code}")
        ts = quote(f"{to_name},{to_code}")
        return f"{BASE}/otn/leftTicket/init?linktypeid=dc&fs={fs}&ts={ts}&date={travel_date}&flag=N,N,Y"


railway = RailwayClient()
