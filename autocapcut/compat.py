"""Chỉnh draft do pycapcut sinh ra cho khớp với bản CapCut đang cài trên máy.

pycapcut viết cứng `platform` là Windows/CapCut 6.7.0. Trên máy khác nền tảng
hoặc khác phiên bản, CapCut đọc thấy sẽ coi đây là draft lạ và có thể chạy bước
chuyển đổi dữ liệu, hoặc từ chối mở.

Cách chắc ăn nhất không phải là đoán, mà là chép lại đúng khối `platform` từ một
draft có sẵn của chính người dùng - trong đó đã có device_id, app_version và os
đúng như CapCut tự ghi. Không có draft nào để tham chiếu thì mới dựng tạm từ
phiên bản đọc được trong app bundle.
"""

from __future__ import annotations

import json
import os
import platform as _platform
import plistlib
import subprocess
from typing import Any, Dict, List, Optional

from .capcut import DRAFT_CONTENT_FILENAME, IS_MACOS, IS_WINDOWS, _run_quiet

CAPCUT_APP_ID = 359289

# Các khoá CapCut luôn ghi nhưng pycapcut bỏ qua. Thiếu thì CapCut vẫn mở được,
# thêm vào cho draft trông giống hàng chính chủ và tránh lỗi ở bản mới.
_MISSING_TOP_LEVEL: Dict[str, Any] = {
    "draft_type": "video",
    "smart_ads_info": {"page_from": "", "routine": "", "draft_url": ""},
    "uneven_animation_template_info": {
        "composition": "", "content": "", "order": "", "sub_template_info_list": [],
    },
    "mixed_track_mode_on": False,
}


def detect_app_version() -> Optional[str]:
    if IS_MACOS:
        plist_path = "/Applications/CapCut.app/Contents/Info.plist"
        try:
            with open(plist_path, "rb") as f:
                return plistlib.load(f).get("CFBundleShortVersionString")
        except (OSError, plistlib.InvalidFileException):
            return None
    if IS_WINDOWS:
        try:
            out = _run_quiet(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-Item (Get-Command CapCut.exe).Source).VersionInfo.ProductVersion"],
                capture_output=True, text=True, timeout=15,
            )
            version = out.stdout.strip()
            return version or None
        except (OSError, subprocess.SubprocessError):
            return None
    return None


def _candidate_drafts(draft_folder: str, exclude: str) -> List[str]:
    """Các draft sẵn có, mới nhất trước - draft mới thì thông tin càng đúng."""
    entries = []
    for name in os.listdir(draft_folder):
        path = os.path.join(draft_folder, name)
        if name.startswith(".") or path == exclude or not os.path.isdir(path):
            continue
        content = os.path.join(path, DRAFT_CONTENT_FILENAME)
        if os.path.isfile(content):
            entries.append((os.path.getmtime(content), content))
    entries.sort(reverse=True)
    return [path for _mtime, path in entries]


def _reference_fields(draft_folder: str, exclude: str) -> Optional[Dict[str, Any]]:
    for path in _candidate_drafts(draft_folder, exclude)[:12]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue  # draft hỏng hoặc bị mã hoá, thử draft kế tiếp

        block = data.get("platform")
        if not isinstance(block, dict) or not block.get("os"):
            continue

        return {
            "platform": block,
            "last_modified_platform": data.get("last_modified_platform", block),
            "new_version": data.get("new_version"),
            "version": data.get("version"),
            "function_assistant_info": data.get("function_assistant_info"),
        }
    return None


def _fallback_platform() -> Dict[str, Any]:
    system = {"Darwin": "mac", "Windows": "windows"}.get(_platform.system(), "mac")
    return {
        "os": system,
        "os_version": _platform.mac_ver()[0] or _platform.release(),
        "app_id": CAPCUT_APP_ID,
        "app_version": detect_app_version() or "9.2.0",
        "app_source": "cc",
    }


def apply_platform_compatibility(draft_path: str, draft_folder: str) -> Dict[str, str]:
    """Vá file draft vừa ghi. Trả về thông tin đã áp dụng để hiển thị cho người dùng."""
    content_path = os.path.join(draft_path, DRAFT_CONTENT_FILENAME)
    try:
        with open(content_path, "r", encoding="utf-8") as f:
            draft = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Không đọc lại được draft vừa ghi: {exc}") from exc

    reference = _reference_fields(draft_folder, exclude=draft_path)
    if reference:
        draft["platform"] = reference["platform"]
        draft["last_modified_platform"] = reference["last_modified_platform"]
        for key in ("new_version", "version", "function_assistant_info"):
            if reference.get(key) is not None:
                draft[key] = reference[key]
        source = "draft có sẵn"
    else:
        block = _fallback_platform()
        draft["platform"] = block
        draft["last_modified_platform"] = block
        source = "phiên bản app cài trên máy"

    for key, value in _MISSING_TOP_LEVEL.items():
        draft.setdefault(key, value)
    draft.setdefault("source", "default")

    with open(content_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False)

    return {
        "os": draft["platform"].get("os", "?"),
        "app_version": draft["platform"].get("app_version", "?"),
        "source": source,
    }
