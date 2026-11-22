from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRAJECTORY_FILE = ROOT / "validation" / "agent_trajectory.json"
_lock = threading.Lock()


def record_trajectory(episode: dict[str, Any]) -> None:
    episode["recorded_at"] = datetime.now().isoformat(timespec="seconds")

    with _lock:
        TRAJECTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        if TRAJECTORY_FILE.exists():
            try:
                records = json.loads(
                    TRAJECTORY_FILE.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                records = []
        else:
            records = []

        if not isinstance(records, list):
            records = []

        records.append(episode)

        TRAJECTORY_FILE.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )