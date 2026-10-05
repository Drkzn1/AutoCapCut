"""Sinh keyframe chuyển động kiểu Ken Burns cho ảnh/video tĩnh.

Hệ toạ độ của CapCut: transform/position tính theo "nửa chiều canvas", tức giá
trị 1.0 = dịch đi đúng nửa chiều rộng (hoặc nửa chiều cao) khung hình. Do đó
đổi từ pixel sang giá trị draft là `px / (canvas / 2)`.

Hệ quả quan trọng: ở mức phóng to `s`, ảnh chỉ được phép trượt tối đa `s - 1.0`
đơn vị về mỗi phía trước khi lộ mép đen. Với s = 1.1 trên canvas 1920x1080, biên
này đúng bằng ±96px ngang và ±54px dọc - chính là lý do biên độ mặc định của
tool là X=190, Y=108 (tổng quãng đường đi, chia đôi cho mỗi phía).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple


class MotionType(Enum):
    ZOOM_IN = "Zoom in"
    ZOOM_OUT = "Zoom out"
    PAN_UP = "Pan up"
    PAN_DOWN = "Pan down"
    PAN_LEFT = "Pan left"
    PAN_RIGHT = "Pan right"

    @property
    def is_pan(self) -> bool:
        return self not in (MotionType.ZOOM_IN, MotionType.ZOOM_OUT)


@dataclass
class MotionSetting:
    """Thông số một kiểu chuyển động, khớp với các ô nhập trong giao diện."""

    enabled: bool = True
    scale_percent: float = 110.0
    """Mức phóng to, tính theo %."""
    amount_x: float = 0.0
    """Tổng quãng đường trượt ngang, tính bằng pixel."""
    amount_y: float = 0.0
    """Tổng quãng đường trượt dọc, tính bằng pixel."""


@dataclass
class MotionConfig:
    enabled: bool = True
    shuffle: bool = True
    """Bật: bốc ngẫu nhiên trong các kiểu đã chọn. Tắt: chạy vòng tròn theo thứ tự."""
    settings: Dict[MotionType, MotionSetting] = field(default_factory=dict)
    seed: Optional[int] = None

    @staticmethod
    def default() -> "MotionConfig":
        return MotionConfig(
            enabled=True,
            shuffle=True,
            settings={
                MotionType.ZOOM_IN: MotionSetting(True, 110.0),
                MotionType.ZOOM_OUT: MotionSetting(True, 110.0),
                MotionType.PAN_UP: MotionSetting(True, 110.0, 0.0, 108.0),
                MotionType.PAN_DOWN: MotionSetting(True, 110.0, 0.0, 108.0),
                MotionType.PAN_LEFT: MotionSetting(True, 110.0, 190.0, 0.0),
                MotionType.PAN_RIGHT: MotionSetting(True, 110.0, 190.0, 0.0),
            },
        )

    def active_types(self) -> List[MotionType]:
        return [t for t in MotionType if self.settings.get(t, MotionSetting(False)).enabled]


@dataclass
class MotionPlan:
    """Kết quả tính toán cho một segment, ở dạng builder có thể áp thẳng."""

    base_scale: float
    """Tỷ lệ phóng giữ cố định suốt segment (dùng cho các kiểu pan)."""
    scale_keyframes: List[Tuple[float, float]] = field(default_factory=list)
    """(tỷ lệ thời gian 0..1, giá trị scale)"""
    position_x_keyframes: List[Tuple[float, float]] = field(default_factory=list)
    position_y_keyframes: List[Tuple[float, float]] = field(default_factory=list)


class MotionPicker:
    """Chọn kiểu chuyển động cho từng scene, tránh lặp lại kiểu vừa dùng."""

    def __init__(self, config: MotionConfig):
        self._config = config
        self._types = config.active_types()
        self._random = random.Random(config.seed)
        self._cursor = 0
        self._previous: Optional[MotionType] = None

    def next(self) -> Optional[MotionType]:
        if not self._config.enabled or not self._types:
            return None

        if self._config.shuffle:
            choices = [t for t in self._types if t is not self._previous] or self._types
            picked = self._random.choice(choices)
        else:
            picked = self._types[self._cursor % len(self._types)]
            self._cursor += 1

        self._previous = picked
        return picked


def build_motion_plan(
    motion: MotionType,
    setting: MotionSetting,
    canvas_width: int,
    canvas_height: int,
) -> MotionPlan:
    """Quy đổi thông số người dùng nhập thành keyframe cụ thể."""
    scale = max(1.0, setting.scale_percent / 100.0)

    if motion is MotionType.ZOOM_IN:
        return MotionPlan(base_scale=1.0, scale_keyframes=[(0.0, 1.0), (1.0, scale)])
    if motion is MotionType.ZOOM_OUT:
        return MotionPlan(base_scale=scale, scale_keyframes=[(0.0, scale), (1.0, 1.0)])

    # Các kiểu pan: giữ nguyên mức phóng, chỉ trượt vị trí.
    half_x = _to_draft_units(setting.amount_x, canvas_width) / 2.0
    half_y = _to_draft_units(setting.amount_y, canvas_height) / 2.0

    # Không cho trượt quá biên an toàn của mức phóng hiện tại, nếu không sẽ lộ
    # mép đen ở đầu hoặc cuối chuyển động.
    limit = max(0.0, scale - 1.0)
    half_x = min(half_x, limit)
    half_y = min(half_y, limit)

    plan = MotionPlan(base_scale=scale)
    if motion is MotionType.PAN_UP:
        plan.position_y_keyframes = [(0.0, -half_y), (1.0, half_y)]
    elif motion is MotionType.PAN_DOWN:
        plan.position_y_keyframes = [(0.0, half_y), (1.0, -half_y)]
    elif motion is MotionType.PAN_LEFT:
        plan.position_x_keyframes = [(0.0, half_x), (1.0, -half_x)]
    elif motion is MotionType.PAN_RIGHT:
        plan.position_x_keyframes = [(0.0, -half_x), (1.0, half_x)]
    return plan


def _to_draft_units(pixels: float, canvas_size: int) -> float:
    if canvas_size <= 0:
        return 0.0
    return pixels / (canvas_size / 2.0)
