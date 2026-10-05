"""Chạy AutoCapCut bằng dòng lệnh - tiện khi cần làm hàng loạt project."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from .builder import BuildRequest, BuildError, build_project
from .media import SortMode
from .motion import MotionConfig, MotionType
from .transcribe import DEFAULT_MODEL, MODEL_SIZES


def _read_scenes(path: Optional[str]) -> str:
    if not path:
        return ""
    if not os.path.isfile(path):
        raise BuildError(f"Không tìm thấy file danh sách scene: {path}")
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise BuildError(f"Không giải mã được file scene: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autocapcut",
        description="Tự động khớp ảnh/video với voice thành một project CapCut.",
    )
    parser.add_argument("--voice", required=True, help="file âm thanh lời đọc")
    parser.add_argument("--srt", help="file phụ đề .srt (bỏ qua nếu dùng --auto-srt)")
    parser.add_argument("--auto-srt", action="store_true",
                        help="tự nhận dạng lời trong file voice thành SRT")
    parser.add_argument("--whisper-model", default=DEFAULT_MODEL, choices=MODEL_SIZES,
                        help="model nhận dạng, càng lớn càng chuẩn và càng chậm")
    parser.add_argument("--language", default="vi",
                        help="mã ngôn ngữ khi nhận dạng, để rỗng thì tự đoán")
    parser.add_argument("--media", required=True, help="thư mục chứa ảnh/video")
    parser.add_argument("--name", required=True, help="tên project CapCut")
    parser.add_argument("--scenes", help="file .txt danh sách scene, mỗi dòng một scene")
    parser.add_argument("--draft-folder", help="thư mục draft của CapCut (mặc định tự dò)")
    parser.add_argument("--size", default="1920x1080", help="khung hình, ví dụ 1080x1920")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--sort", default=SortMode.NATURAL.name,
                        choices=[m.name for m in SortMode],
                        help="cách sắp xếp file media")
    parser.add_argument("--no-subtitles", action="store_true", help="không chèn phụ đề")
    parser.add_argument("--no-motion", action="store_true", help="tắt keyframe chuyển động")
    parser.add_argument("--no-shuffle", action="store_true",
                        help="chạy các kiểu chuyển động lần lượt thay vì ngẫu nhiên")
    parser.add_argument("--motion-types", help="danh sách kiểu chuyển động, ngăn bằng dấu phẩy: "
                                               + ",".join(m.name for m in MotionType))
    parser.add_argument("--scale", type=float, help="mức phóng to chung, tính theo %%")
    parser.add_argument("--overwrite", action="store_true", help="ghi đè project trùng tên")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        width, height = (int(v) for v in args.size.lower().split("x", 1))
    except ValueError:
        print(f"Khung hình không hợp lệ: {args.size} (ví dụ đúng: 1920x1080)", file=sys.stderr)
        return 2

    motion = MotionConfig.default()
    motion.enabled = not args.no_motion
    motion.shuffle = not args.no_shuffle
    if args.motion_types:
        wanted = {t.strip().upper() for t in args.motion_types.split(",") if t.strip()}
        unknown = wanted - {m.name for m in MotionType}
        if unknown:
            print(f"Kiểu chuyển động không tồn tại: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        for kind, setting in motion.settings.items():
            setting.enabled = kind.name in wanted
    if args.scale is not None:
        for setting in motion.settings.values():
            setting.scale_percent = args.scale

    try:
        scenes_text = _read_scenes(args.scenes)
    except BuildError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1

    request = BuildRequest(
        audio_path=os.path.abspath(args.voice),
        srt_path=os.path.abspath(args.srt) if args.srt else "",
        auto_srt=args.auto_srt or not args.srt,
        whisper_model=args.whisper_model,
        language=args.language or None,
        scenes_text=scenes_text,
        media_folder=os.path.abspath(args.media),
        draft_name=args.name,
        draft_folder=os.path.abspath(args.draft_folder) if args.draft_folder else None,
        width=width,
        height=height,
        fps=args.fps,
        burn_subtitles=not args.no_subtitles,
        sort_mode=SortMode[args.sort],
        motion=motion,
        overwrite=args.overwrite,
    )

    try:
        result = build_project(request, progress=lambda m: print(m))
    except (BuildError, OSError, ValueError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"Xong: {result.draft_name}")
    print(f"  {result.scene_count} scene · {result.media_count} media "
          f"· {result.duration / 1_000_000:.1f} giây")
    print(f"  {result.draft_path}")
    for warning in result.warnings:
        print(f"  [Lưu ý] {warning}")
    return 0
