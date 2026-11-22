TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_train_tickets",
            "description": "查询12306官方余票和票价",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_station": {"type": "string"},
                    "to_station": {"type": "string"},
                    "travel_date": {"type": "string"},
                    "passengers": {"type": "integer"},
                    "seat_types": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": [
                    "from_station",
                    "to_station",
                    "travel_date"
                ]
            }
        }
    }
]