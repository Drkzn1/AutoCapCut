"""Sinh file icon .icns cho app từ hình vẽ bằng PIL.

macOS đòi một thư mục .iconset chứa đủ các cỡ rồi mới dựng được .icns, nên
script vẽ từng cỡ một thay vì phóng to một ảnh duy nhất - phóng to sẽ vỡ nét ở
cỡ nhỏ, icon trong Dock nhìn sẽ nhoè.
"""

import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
ICONSET = os.path.join(BASE, "build", "AutoCapCut.iconset")
ICNS = os.path.join(BASE, "build", "AutoCapCut.icns")

BACKGROUND = (35, 38, 45)
ACCENT = (47, 111, 208)
LIGHT = (232, 236, 242)


def draw_icon(size: int) -> Image.Image:
    # Vẽ ở 4x rồi thu nhỏ để bo góc và cạnh xiên được mượt
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    margin = s * 0.06
    d.rounded_rectangle([margin, margin, s - margin, s - margin],
                        radius=s * 0.22, fill=BACKGROUND)

    # Dải phim ở nửa trên: tượng trưng cho media đầu vào
    strip_h = s * 0.20
    strip_y = s * 0.26
    d.rounded_rectangle([s * 0.20, strip_y, s * 0.80, strip_y + strip_h],
                        radius=s * 0.03, fill=LIGHT)
    hole_w, hole_h = s * 0.045, s * 0.05
    for i in range(4):
        x = s * 0.255 + i * s * 0.155
        d.rectangle([x, strip_y + strip_h * 0.28, x + hole_w, strip_y + strip_h * 0.28 + hole_h],
                    fill=BACKGROUND)

    # Sóng âm ở nửa dưới: tượng trưng cho voice được khớp vào
    bar_w = s * 0.052
    heights = [0.10, 0.19, 0.30, 0.22, 0.13, 0.24, 0.16]
    base_y = s * 0.78
    for i, h in enumerate(heights):
        x = s * 0.215 + i * (bar_w + s * 0.037)
        d.rounded_rectangle([x, base_y - s * h, x + bar_w, base_y],
                            radius=bar_w / 2, fill=ACCENT)

    return img.resize((size, size), Image.LANCZOS)


def main() -> int:
    if os.path.exists(ICONSET):
        shutil.rmtree(ICONSET)
    os.makedirs(ICONSET)

    # Bộ cỡ macOS yêu cầu, mỗi cỡ có thêm bản @2x cho màn Retina
    for size in (16, 32, 64, 128, 256, 512):
        draw_icon(size).save(os.path.join(ICONSET, f"icon_{size}x{size}.png"))
        draw_icon(size * 2).save(os.path.join(ICONSET, f"icon_{size}x{size}@2x.png"))

    result = subprocess.run(["iconutil", "-c", "icns", ICONSET, "-o", ICNS],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print("iconutil lỗi:", result.stderr, file=sys.stderr)
        return 1

    print("đã tạo", ICNS)
    build_ico()
    return 0


def build_ico(path: str = None) -> str:
    """Xuất thêm bản .ico cho Windows.

    Windows lấy sẵn nhiều cỡ trong một file .ico, nên nhúng đủ bộ để icon nét
    ở cả thanh taskbar lẫn cửa sổ chọn file.
    """
    path = path or os.path.join(BASE, "build", "AutoCapCut.ico")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base = draw_icon(256)
    base.save(path, format="ICO", sizes=[(s, s) for s in sizes])
    print("đã tạo", path)
    return path


if __name__ == "__main__":
    sys.exit(main())
