"""Quét thư mục ảnh/video và quyết định file nào ứng với scene nào."""

from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".mpg", ".mpeg"}

_NUMBER_CHUNK = re.compile(r"(\d+)")


class SortMode(Enum):
    NATURAL = "Sắp xếp media theo ABC"
    NUMBER_IN_NAME = "Sắp xếp theo số trong tên file"
    MODIFIED_TIME = "Sắp xếp theo ngày sửa file"
    RANDOM = "Xáo trộn ngẫu nhiên"


@dataclass
class MediaFile:
    path: str
    is_video: bool

    @property
    def name(self) -> str:
        return os.path.basename(self.path)


def _natural_key(name: str):
    """"anh2.jpg" đứng trước "anh10.jpg" thay vì ngược lại."""
    parts = _NUMBER_CHUNK.split(name.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def _leading_number(name: str) -> Optional[int]:
    m = _NUMBER_CHUNK.search(os.path.basename(name))
    return int(m.group(1)) if m else None


def scan_media_folder(
    folder: str,
    sort_mode: SortMode = SortMode.NATURAL,
    seed: Optional[int] = None,
) -> List[MediaFile]:
    """Liệt kê ảnh/video trong thư mục (không đệ quy) theo thứ tự đã chọn."""
    if not os.path.isdir(folder):
        raise NotADirectoryError(f"Thư mục media không tồn tại: {folder}")

    files: List[MediaFile] = []
    for entry in os.listdir(folder):
        if entry.startswith("."):
            continue
        path = os.path.join(folder, entry)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(entry)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            files.append(MediaFile(path, is_video=False))
        elif ext in VIDEO_EXTENSIONS:
            files.append(MediaFile(path, is_video=True))

    if sort_mode is SortMode.NATURAL:
        files.sort(key=lambda f: _natural_key(f.name))
    elif sort_mode is SortMode.NUMBER_IN_NAME:
        # File không có số trong tên bị đẩy xuống cuối, giữ nguyên thứ tự ABC
        files.sort(key=lambda f: (_leading_number(f.name) is None,
                                  _leading_number(f.name) or 0,
                                  _natural_key(f.name)))
    elif sort_mode is SortMode.MODIFIED_TIME:
        files.sort(key=lambda f: os.path.getmtime(f.path))
    elif sort_mode is SortMode.RANDOM:
        random.Random(seed).shuffle(files)

    return files


def assign_media_to_scenes(
    media: Sequence[MediaFile], scene_count: int
) -> List[MediaFile]:
    """Ghép media theo thứ tự: file 1 -> scene 1, file 2 -> scene 2...

    Thiếu file thì quay vòng lại từ đầu, thừa file thì bỏ phần dư. Cả hai trường
    hợp đều được builder ghi vào log để người dùng biết.
    """
    if not media:
        raise ValueError("Thư mục media không có ảnh hoặc video nào.")
    return [media[i % len(media)] for i in range(scene_count)]
