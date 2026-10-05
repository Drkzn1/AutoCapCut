"""Ghép mọi thứ lại: voice + SRT + scene + media -> một project CapCut hoàn chỉnh."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from pycapcut import (
    AudioMaterial,
    AudioSegment,
    ClipSettings,
    KeyframeProperty,
    ScriptFile,
    TextSegment,
    TextStyle,
    Timerange,
    TrackType,
    VideoMaterial,
    VideoSegment,
)

from . import capcut, compat, transcribe
from .media import MediaFile, SortMode, assign_media_to_scenes, scan_media_folder
from .motion import MotionConfig, MotionPicker, MotionPlan, build_motion_plan
from .scenes import Scene, align_scenes_to_srt, parse_scenes
from .srt import SrtBlock, parse_srt

ONE_FRAME_30FPS = 33_333

VIDEO_TRACK = "media"
AUDIO_TRACK = "voice"
TEXT_TRACK = "phude"

ProgressCallback = Callable[[str], None]


@dataclass
class BuildRequest:
    audio_path: str
    srt_path: str
    scenes_text: str
    media_folder: str
    draft_name: str

    draft_folder: Optional[str] = None
    width: int = 1920
    height: int = 1080
    fps: int = 30

    burn_subtitles: bool = True
    subtitle_size: float = 5.0
    subtitle_offset_y: float = -0.8

    auto_srt: bool = False
    """Tự nhận dạng lời trong file voice thành SRT khi chưa có sẵn file SRT."""
    whisper_model: str = transcribe.DEFAULT_MODEL
    language: Optional[str] = "vi"

    sort_mode: SortMode = SortMode.NATURAL
    motion: MotionConfig = field(default_factory=MotionConfig.default)
    mute_source_video: bool = True
    overwrite: bool = False


@dataclass
class BuildResult:
    draft_path: str
    draft_name: str
    scene_count: int
    media_count: int
    duration: int
    registered: bool
    srt_path: str = ""
    """File SRT đã dùng - trỏ tới file tự sinh nếu bật nhận dạng giọng nói."""
    warnings: List[str] = field(default_factory=list)


class BuildError(RuntimeError):
    pass


def build_project(request: BuildRequest, progress: Optional[ProgressCallback] = None) -> BuildResult:
    log = progress or (lambda _msg: None)
    warnings: List[str] = []

    _validate(request)

    draft_folder = request.draft_folder or capcut.find_draft_folder()
    if not draft_folder:
        raise BuildError(
            "Không tìm thấy thư mục draft của CapCut. Hãy mở CapCut tạo thử một dự án, "
            "hoặc chọn thủ công đường dẫn thư mục draft."
        )

    log("Đang đọc file voice...")
    audio_material = AudioMaterial(request.audio_path)
    audio_duration = audio_material.duration

    srt_path = request.srt_path
    if request.auto_srt and not srt_path:
        # Ghi ra file cạnh voice thay vì giữ trong bộ nhớ: nhận dạng máy luôn
        # sai đôi chỗ, người dùng cần mở ra sửa rồi chạy lại mà không phải
        # nhận dạng lần nữa
        try:
            srt_path = transcribe.transcribe_to_srt(
                request.audio_path,
                model_size=request.whisper_model,
                language=request.language,
                progress=log,
            )
        except transcribe.TranscribeError as exc:
            raise BuildError(str(exc)) from exc
        warnings.append(f"SRT tự nhận dạng đã lưu tại {srt_path} - nên mở ra soát lại.")

    log("Đang đọc file SRT...")
    blocks = parse_srt(srt_path)
    if not blocks:
        raise BuildError("File SRT không có phụ đề nào đọc được.")

    log("Đang quét thư mục media...")
    media_files = scan_media_folder(request.media_folder, request.sort_mode)

    scenes = parse_scenes(request.scenes_text)
    if not scenes:
        # Không nhập scene thì mỗi file media tự thành một scene, chia theo SRT
        scenes = [Scene(i + 1, "") for i in range(len(media_files))]
        warnings.append(
            f"Chưa nhập danh sách scene nên tool chia đều {len(blocks)} câu phụ đề "
            f"cho {len(media_files)} file media."
        )

    log(f"Đang khớp {len(scenes)} scene với {len(blocks)} câu phụ đề...")
    scenes = align_scenes_to_srt(scenes, blocks, total_duration=audio_duration)

    assigned = assign_media_to_scenes(media_files, len(scenes))
    if len(media_files) < len(scenes):
        warnings.append(
            f"Chỉ có {len(media_files)} file media cho {len(scenes)} scene "
            f"- tool đã dùng lại media từ đầu cho các scene còn thiếu."
        )
    elif len(media_files) > len(scenes):
        warnings.append(
            f"Có {len(media_files)} file media nhưng chỉ {len(scenes)} scene "
            f"- {len(media_files) - len(scenes)} file cuối không được dùng."
        )

    log("Đang dựng timeline...")
    script = ScriptFile(request.width, request.height, request.fps)
    script.add_track(TrackType.video, VIDEO_TRACK)
    script.add_track(TrackType.audio, AUDIO_TRACK)

    script.add_segment(
        AudioSegment(audio_material, Timerange(0, audio_duration)),
        AUDIO_TRACK,
    )

    picker = MotionPicker(request.motion)
    for scene, media in zip(scenes, assigned):
        _add_scene_segments(script, scene, media, picker, request, warnings)

    if request.burn_subtitles:
        log("Đang chèn phụ đề...")
        _add_subtitles(script, blocks, request)

    log("Đang ghi draft...")
    draft_path = capcut.prepare_draft_folder(
        draft_folder, request.draft_name, overwrite=request.overwrite
    )
    capcut.write_draft_content(draft_path, script)

    applied = compat.apply_platform_compatibility(draft_path, draft_folder)
    log(f"Đã đặt draft theo CapCut {applied['app_version']} ({applied['os']}, "
        f"lấy từ {applied['source']})")

    total_duration = max(audio_duration, scenes[-1].end if scenes else 0)
    registered = capcut.register_in_root_meta(draft_folder, draft_path, total_duration)
    if not registered:
        warnings.append(
            "Không thấy file danh mục root_meta_info.json - draft đã tạo xong nhưng "
            "có thể phải khởi động lại CapCut mới thấy."
        )
    if capcut.is_capcut_running():
        warnings.append(
            "CapCut đang chạy. Hãy thoát hẳn CapCut rồi mở lại, nếu không dự án mới "
            "có thể không hiện ra (CapCut ghi đè danh mục khi thoát)."
        )

    return BuildResult(
        draft_path=draft_path,
        draft_name=os.path.basename(draft_path),
        scene_count=len(scenes),
        media_count=len(media_files),
        duration=total_duration,
        registered=registered,
        srt_path=srt_path,
        warnings=warnings,
    )


def _validate(request: BuildRequest) -> None:
    if not request.audio_path or not os.path.isfile(request.audio_path):
        raise BuildError("Chưa chọn file voice hợp lệ.")
    if not request.srt_path:
        if not request.auto_srt:
            raise BuildError(
                "Chưa chọn file SRT. Hoặc chọn file, hoặc bật 'Tự tạo phụ đề từ voice'."
            )
        if not transcribe.is_available():
            raise BuildError(
                "Bật tự tạo phụ đề nhưng chưa cài faster-whisper. "
                "Chạy: .venv/bin/pip install faster-whisper"
            )
    elif not os.path.isfile(request.srt_path):
        raise BuildError("File SRT không tồn tại.")
    if not request.media_folder or not os.path.isdir(request.media_folder):
        raise BuildError("Chưa chọn thư mục ảnh/video hợp lệ.")
    if not request.draft_name.strip():
        raise BuildError("Chưa đặt tên cho dự án CapCut.")
    if any(ch in request.draft_name for ch in '/\\:*?"<>|'):
        raise BuildError('Tên dự án không được chứa các ký tự / \\ : * ? " < > |')


def _add_scene_segments(
    script: ScriptFile,
    scene: Scene,
    media: MediaFile,
    picker: MotionPicker,
    request: BuildRequest,
    warnings: List[str],
) -> None:
    try:
        material = VideoMaterial(media.path)
    except Exception as exc:  # pymediainfo ném đủ loại lỗi tuỳ định dạng
        raise BuildError(f"Không đọc được file media {media.name}: {exc}") from exc

    # Loại lấy từ chính material chứ không suy từ đuôi file: GIF có đuôi ảnh
    # nhưng CapCut coi là video, và ảnh chụp đôi khi mang đuôi lạ.
    is_video = material.material_type == "video"

    motion_type = picker.next()
    plan: Optional[MotionPlan] = None
    if motion_type is not None:
        setting = request.motion.settings[motion_type]
        plan = build_motion_plan(motion_type, setting, request.width, request.height)

    for start, duration, span in _split_scene(scene, material, is_video):
        clip = ClipSettings(scale_x=plan.base_scale, scale_y=plan.base_scale) if plan else None
        segment = VideoSegment(
            material,
            Timerange(start, duration),
            source_timerange=Timerange(0, duration) if is_video else None,
            volume=0.0 if (is_video and request.mute_source_video) else 1.0,
            clip_settings=clip,
        )
        if plan:
            _apply_motion(segment, plan, duration, span)
        script.add_segment(segment, VIDEO_TRACK)


def _split_scene(
    scene: Scene, material: VideoMaterial, is_video: bool
) -> List[Tuple[int, int, Tuple[float, float]]]:
    """Chia scene thành các segment thực tế.

    Ảnh luôn ra đúng một segment. Video ngắn hơn scene thì phải lặp lại nhiều
    lần cho đủ dài - phát chậm lại sẽ trông giả, còn để hụt thì lộ khung đen.

    Trả về danh sách (mốc bắt đầu, độ dài, khoảng thời gian tương đối trong
    scene) - phần cuối để nội suy keyframe cho liền mạch giữa các lần lặp.
    """
    total = scene.duration
    if not is_video or material.duration >= total:
        return [(scene.start, total, (0.0, 1.0))]

    pieces: List[Tuple[int, int, Tuple[float, float]]] = []
    elapsed = 0
    while elapsed < total:
        piece = min(material.duration, total - elapsed)
        if piece < ONE_FRAME_30FPS:
            break  # phần dư ngắn hơn 1 frame, kéo dài segment trước đó thay vì thêm mới
        pieces.append((
            scene.start + elapsed,
            piece,
            (elapsed / total, (elapsed + piece) / total),
        ))
        elapsed += piece

    if not pieces:
        return [(scene.start, total, (0.0, 1.0))]

    # Bù phần dư bị bỏ ở trên vào segment cuối để scene khít đúng thời lượng
    last_start, last_duration, last_span = pieces[-1]
    filled = last_start + last_duration
    if filled < scene.end:
        pieces[-1] = (last_start, scene.end - last_start, (last_span[0], 1.0))
    return pieces


def _apply_motion(
    segment: VideoSegment, plan: MotionPlan, duration: int, span: Tuple[float, float]
) -> None:
    """Đặt keyframe đầu/cuối segment, lấy giá trị nội suy theo vị trí trong scene."""
    start_fraction, end_fraction = span
    for keyframes, prop in (
        (plan.scale_keyframes, KeyframeProperty.uniform_scale),
        (plan.position_x_keyframes, KeyframeProperty.position_x),
        (plan.position_y_keyframes, KeyframeProperty.position_y),
    ):
        if not keyframes:
            continue
        segment.add_keyframe(prop, 0, _sample(keyframes, start_fraction))
        segment.add_keyframe(prop, max(duration - 1, 0), _sample(keyframes, end_fraction))


def _sample(keyframes: Sequence[Tuple[float, float]], fraction: float) -> float:
    """Nội suy tuyến tính giá trị keyframe tại một vị trí bất kỳ trong scene."""
    if len(keyframes) == 1:
        return keyframes[0][1]
    (t0, v0), (t1, v1) = keyframes[0], keyframes[-1]
    if t1 <= t0:
        return v1
    ratio = min(1.0, max(0.0, (fraction - t0) / (t1 - t0)))
    return v0 + (v1 - v0) * ratio


def _add_subtitles(script: ScriptFile, blocks: Sequence[SrtBlock], request: BuildRequest) -> None:
    script.add_track(TrackType.text, TEXT_TRACK, relative_index=999)
    style = TextStyle(size=request.subtitle_size, align=1, auto_wrapping=True)
    clip = ClipSettings(transform_y=request.subtitle_offset_y)
    for block in blocks:
        if not block.text:
            continue
        script.add_segment(
            TextSegment(
                block.text,
                Timerange(block.start, block.duration),
                style=style,
                clip_settings=clip,
            ),
            TEXT_TRACK,
        )
