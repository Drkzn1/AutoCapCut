"""Đọc file SRT thành danh sách block có mốc thời gian (đơn vị micro giây)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

# 00:01:23,456  hoặc  00:01:23.456
_TIME = re.compile(r"(\d+):(\d{1,2}):(\d{1,2})[,.](\d{1,3})")
_ARROW = re.compile(r"-->")


@dataclass
class SrtBlock:
    index: int
    start: int
    """micro giây"""
    end: int
    """micro giây"""
    text: str

    @property
    def duration(self) -> int:
        return self.end - self.start


def _parse_timestamp(raw: str) -> int:
    m = _TIME.search(raw)
    if not m:
        raise ValueError(f"Không đọc được mốc thời gian: {raw!r}")
    h, mi, s, ms = m.groups()
    ms = ms.ljust(3, "0")  # ",5" -> 500ms
    return ((int(h) * 3600 + int(mi) * 60 + int(s)) * 1000 + int(ms)) * 1000


def _read_text(path: str) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Không giải mã được file SRT: {path}")


def parse_srt(path: str) -> List[SrtBlock]:
    """Đọc file SRT. Bỏ qua block hỏng thay vì làm sập cả file."""
    raw = _read_text(path).replace("\r\n", "\n").replace("\r", "\n")
    blocks: List[SrtBlock] = []

    for chunk in re.split(r"\n\s*\n", raw):
        lines = [ln for ln in chunk.split("\n") if ln.strip()]
        if not lines:
            continue

        # Dòng đầu có thể là số thứ tự, hoặc đã là dòng thời gian luôn
        cursor = 0
        if not _ARROW.search(lines[0]):
            cursor = 1
        if cursor >= len(lines) or not _ARROW.search(lines[cursor]):
            continue

        try:
            left, right = _ARROW.split(lines[cursor], 1)
            start, end = _parse_timestamp(left), _parse_timestamp(right)
        except ValueError:
            continue

        text = " ".join(ln.strip() for ln in lines[cursor + 1:]).strip()
        blocks.append(SrtBlock(len(blocks) + 1, start, end, text))

    blocks.sort(key=lambda b: b.start)

    # Vá các block bị chồng lấn / lùi thời gian
    for i in range(len(blocks) - 1):
        if blocks[i].end > blocks[i + 1].start:
            blocks[i].end = blocks[i + 1].start
    return [b for b in blocks if b.end > b.start]
