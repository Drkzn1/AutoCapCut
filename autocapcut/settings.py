"""Ghi nhớ lựa chọn của người dùng giữa các lần mở tool."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".autocapcut")
CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.json")


def load_settings() -> Dict[str, Any]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        # File cấu hình hỏng không đáng để chặn người dùng mở tool
        return {}


def save_settings(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
