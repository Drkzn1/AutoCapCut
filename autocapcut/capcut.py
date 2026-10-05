"""Ghi draft ra đúng chỗ CapCut đọc, và đăng ký để nó hiện trong màn hình dự án.

Khác biệt quan trọng giữa hai hệ điều hành: bản Windows đọc `draft_content.json`,
bản macOS đọc `draft_info.json`. Thư viện pycapcut mặc định ghi theo kiểu Windows
nên ở đây phải đổi tên file cho đúng nền tảng.

Ngoài thư mục draft, CapCut còn giữ một file danh mục `root_meta_info.json`. Nếu
không thêm bản ghi vào đó thì draft vẫn hợp lệ nhưng không hiện trên màn hình
chính, người dùng sẽ tưởng tool chạy hỏng.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

DRAFT_CONTENT_FILENAME = "draft_content.json" if IS_WINDOWS else "draft_info.json"
ROOT_META_FILENAME = "root_meta_info.json"


class CapCutError(RuntimeError):
    pass


# Trên Windows, app chạy ở chế độ cửa sổ mà gọi tiến trình con sẽ làm nháy một
# cửa sổ console đen. Cờ này bảo Windows đừng cấp console cho tiến trình con.
_NO_WINDOW = {"creationflags": 0x08000000} if IS_WINDOWS else {}


def _run_quiet(command, **kwargs):
    """Chạy lệnh ngoài mà không làm nháy cửa sổ console trên Windows."""
    return subprocess.run(command, **kwargs, **_NO_WINDOW)


def default_draft_folders() -> List[str]:
    """Các vị trí thư mục draft thường gặp, xếp theo thứ tự ưu tiên."""
    home = os.path.expanduser("~")
    candidates: List[str] = []

    if IS_MACOS:
        candidates += [
            os.path.join(home, "Movies", "CapCut", "User Data", "Projects", "com.lveditor.draft"),
            os.path.join(home, "Movies", "JianyingPro", "User Data", "Projects", "com.lveditor.draft"),
        ]
    elif IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
        candidates += [
            os.path.join(local, "CapCut", "User Data", "Projects", "com.lveditor.draft"),
            os.path.join(local, "JianyingPro", "User Data", "Projects", "com.lveditor.draft"),
        ]
    return candidates


def find_draft_folder() -> Optional[str]:
    for path in default_draft_folders():
        if os.path.isdir(path):
            return path
    return None


def is_capcut_running() -> bool:
    """CapCut đang mở sẽ ghi đè root_meta_info.json khi thoát, làm mất bản ghi mới."""
    try:
        if IS_MACOS:
            out = _run_quiet(["pgrep", "-x", "CapCut"], capture_output=True, timeout=5)
            return out.returncode == 0
        if IS_WINDOWS:
            out = _run_quiet(
                ["tasklist", "/FI", "IMAGENAME eq CapCut.exe"],
                capture_output=True, text=True, timeout=10,
            )
            return "CapCut.exe" in out.stdout
    except (OSError, subprocess.SubprocessError):
        pass
    return False


def _now_microseconds() -> int:
    return int(time.time() * 1_000_000)


def _unique_draft_name(folder: str, name: str) -> str:
    """CapCut phân biệt dự án bằng tên thư mục, nên không cho phép trùng."""
    candidate, counter = name, 1
    while os.path.exists(os.path.join(folder, candidate)):
        candidate = f"{name} ({counter})"
        counter += 1
    return candidate


def prepare_draft_folder(folder: str, draft_name: str, overwrite: bool = False) -> str:
    """Tạo thư mục draft rỗng kèm draft_meta_info.json, trả về đường dẫn."""
    if not os.path.isdir(folder):
        raise CapCutError(f"Không tìm thấy thư mục draft của CapCut: {folder}")

    if not overwrite:
        draft_name = _unique_draft_name(folder, draft_name)

    draft_path = os.path.join(folder, draft_name)
    if os.path.exists(draft_path):
        shutil.rmtree(draft_path)
    os.makedirs(draft_path)

    _write_draft_meta(folder, draft_path, draft_name)
    return draft_path


def _meta_template() -> Dict[str, Any]:
    from pycapcut import assets  # nội bộ pycapcut, chỉ dùng để lấy file mẫu

    with open(assets.get_asset_path("DRAFT_META_TEMPLATE"), "r", encoding="utf-8") as f:
        return json.load(f)


def _write_draft_meta(root_folder: str, draft_path: str, draft_name: str) -> Dict[str, Any]:
    meta = _meta_template()
    now = _now_microseconds()
    meta.update({
        "draft_id": str(uuid.uuid4()).upper(),
        "draft_name": draft_name,
        "draft_fold_path": draft_path,
        "draft_root_path": root_folder,
        "draft_cover": "draft_cover.jpg",
        "draft_removable_storage_device": "",
        "tm_draft_create": now,
        "tm_draft_modified": now,
        "tm_draft_removed": 0,
    })
    with open(os.path.join(draft_path, "draft_meta_info.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=4)
    return meta


def write_draft_content(draft_path: str, script_file) -> str:
    """Ghi timeline ra file mà CapCut trên nền tảng hiện tại thực sự đọc."""
    target = os.path.join(draft_path, DRAFT_CONTENT_FILENAME)
    script_file.dump(target)
    return target


def register_in_root_meta(root_folder: str, draft_path: str, duration: int) -> bool:
    """Thêm draft vào danh mục để CapCut hiển thị nó. Trả về False nếu bỏ qua.

    Không tìm thấy file danh mục thì coi như bản CapCut này tự quét thư mục -
    đó không phải lỗi, nên chỉ báo lại chứ không dừng cả quá trình.
    """
    root_meta_path = os.path.join(root_folder, ROOT_META_FILENAME)
    if not os.path.exists(root_meta_path):
        return False

    try:
        with open(root_meta_path, "r", encoding="utf-8") as f:
            root_meta = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise CapCutError(f"Không đọc được {ROOT_META_FILENAME}: {exc}") from exc

    with open(os.path.join(draft_path, "draft_meta_info.json"), "r", encoding="utf-8") as f:
        draft_meta = json.load(f)

    draft_name = os.path.basename(draft_path)
    now = _now_microseconds()
    entry = {
        "cloud_draft_cover": False,
        "cloud_draft_sync": False,
        "draft_cloud_last_action_download": False,
        "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": os.path.join(draft_path, "draft_cover.jpg"),
        "draft_fold_path": draft_path,
        "draft_id": draft_meta["draft_id"],
        "draft_is_ai_shorts": False,
        "draft_is_cloud_temp_draft": False,
        "draft_is_invisible": False,
        "draft_json_file": os.path.join(draft_path, DRAFT_CONTENT_FILENAME),
        "draft_name": draft_name,
        "draft_new_version": "",
        "draft_root_path": root_folder,
        "draft_timeline_materials_size": 0,
        "draft_type": "",
        "tm_draft_create": draft_meta.get("tm_draft_create", now),
        "tm_draft_modified": now,
        "tm_draft_removed": 0,
        "tm_duration": duration,
    }

    store = root_meta.setdefault("all_draft_store", [])
    # Giữ nguyên vị trí nếu bản ghi đã tồn tại (trường hợp ghi đè draft cũ)
    for i, existing in enumerate(store):
        if existing.get("draft_fold_path") == draft_path:
            store[i] = entry
            break
    else:
        store.insert(0, entry)

    backup = root_meta_path + ".autocapcut.bak"
    if not os.path.exists(backup):
        shutil.copy2(root_meta_path, backup)

    # Ghi qua file tạm rồi đổi tên: nếu tool bị tắt giữa chừng, danh mục gốc của
    # CapCut vẫn nguyên vẹn thay vì thành file JSON cụt.
    temp_path = root_meta_path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(root_meta, f, ensure_ascii=False, indent=4)
    os.replace(temp_path, root_meta_path)
    return True
