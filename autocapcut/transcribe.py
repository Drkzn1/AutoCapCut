"""Tự tạo file SRT từ file voice bằng faster-whisper.

Dùng khi người dùng chỉ có file lời đọc mà chưa có phụ đề. Model được tải về
lần đầu rồi nằm lại trong cache, các lần sau chạy offline.

Lưu ý về chất lượng với tiếng Việt: model `base` chạy rất nhanh nhưng hay sai
dấu và sai từ. Bản thân việc khớp scene không bị ảnh hưởng nhiều vì thuật toán
so khớp đã bỏ dấu trước khi so sánh, nhưng phụ đề chèn vào video thì nên dùng
`small` trở lên.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, List, Optional

MODEL_SIZES = ["tiny", "base", "small", "medium", "large-v3"]
DEFAULT_MODEL = "small"

# Whisper hay trả về cả đoạn dài chục giây trong một segment. Để nguyên thì phụ
# đề thành một khối chữ đứng yên suốt đoạn, và việc khớp scene cũng mất chỗ bám
# vì cả kịch bản chỉ có đúng một mốc thời gian. Vì vậy phải lấy mốc theo từng từ
# rồi tự cắt lại theo các ngưỡng dưới đây.
MAX_LINE_CHARS = 45
MAX_LINE_SECONDS = 6.0
PAUSE_BREAK_SECONDS = 0.5
"""Im lặng dài hơn ngưỡng này giữa hai từ thì coi như hết câu."""
MIN_CHARS_BEFORE_COMMA_BREAK = 20
"""Chỉ ngắt ở dấu phẩy khi dòng đã đủ dài, tránh cắt vụn."""

_SENTENCE_END = (".", "!", "?", "…", ":", ";")
_SOFT_BREAK = (",",)

# Nơi cache model, để không rải vào thư mục cache chung của HuggingFace
MODEL_CACHE = os.path.join(os.path.expanduser("~"), ".autocapcut", "models")

ProgressCallback = Callable[[str], None]


class TranscribeError(RuntimeError):
    pass


@dataclass
class TranscribedSegment:
    start: float
    """giây"""
    end: float
    """giây"""
    text: str


def is_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def _format_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rest = divmod(total_ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def segments_to_srt(segments: List[TranscribedSegment]) -> str:
    lines = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{_format_timestamp(seg.start)} --> {_format_timestamp(seg.end)}")
        lines.append(seg.text.strip())
        lines.append("")
    return "\n".join(lines)


def transcribe(
    audio_path: str,
    model_size: str = DEFAULT_MODEL,
    language: Optional[str] = "vi",
    progress: Optional[ProgressCallback] = None,
) -> List[TranscribedSegment]:
    """Nhận dạng lời trong file audio, trả về các đoạn đã có mốc thời gian.

    Args:
        audio_path: file voice.
        model_size: một trong `MODEL_SIZES`. Càng lớn càng chuẩn và càng chậm.
        language: mã ngôn ngữ, ví dụ "vi". Để None thì Whisper tự đoán.
    """
    log = progress or (lambda _m: None)

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscribeError(
            "Chưa cài faster-whisper. Chạy: .venv/bin/pip install faster-whisper"
        ) from exc

    if not os.path.isfile(audio_path):
        raise TranscribeError(f"Không tìm thấy file voice: {audio_path}")

    os.makedirs(MODEL_CACHE, exist_ok=True)
    log(f"Đang nạp model Whisper '{model_size}' (lần đầu sẽ tải về, hơi lâu)...")

    try:
        # int8 trên CPU: nhanh gấp nhiều lần float32 mà sai lệch không đáng kể
        model = WhisperModel(model_size, device="cpu", compute_type="int8",
                             download_root=MODEL_CACHE)
    except Exception as exc:
        raise TranscribeError(f"Không nạp được model '{model_size}': {exc}") from exc

    log("Đang nhận dạng giọng nói...")
    try:
        raw_segments, info = model.transcribe(
            audio_path,
            language=language or None,
            beam_size=5,
            # Mốc theo từng từ là cơ sở để tự cắt câu ở bước sau
            word_timestamps=True,
            # Cắt bỏ khoảng lặng giúp mốc thời gian bám sát lời nói hơn, tránh
            # phụ đề hiện sớm hoặc kéo dài lê thê qua đoạn im lặng
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
    except Exception as exc:
        raise TranscribeError(f"Nhận dạng thất bại: {exc}") from exc

    detected = getattr(info, "language", None)
    if detected and not language:
        log(f"Ngôn ngữ nhận ra: {detected}")

    words: List[_Word] = []
    fallback: List[TranscribedSegment] = []
    for seg in raw_segments:  # generator - việc nhận dạng chạy dần ở đây
        for word in (getattr(seg, "words", None) or []):
            text = word.word.strip()
            if text:
                words.append(_Word(word.start, word.end, text))
        text = seg.text.strip()
        if text:
            fallback.append(TranscribedSegment(seg.start, seg.end, text))
        if fallback and len(fallback) % 10 == 0:
            log(f"  ...đã nhận dạng {len(fallback)} đoạn")

    # Model nhỏ đôi khi không trả về mốc theo từ; khi đó đành dùng đoạn thô
    results = _split_into_lines(words) if words else fallback

    if not results:
        raise TranscribeError("Không nhận ra câu nào trong file voice.")

    log(f"Xong: {len(results)} câu.")
    return results


@dataclass
class _Word:
    start: float
    end: float
    text: str


def _split_into_lines(words: List[_Word]) -> List[TranscribedSegment]:
    """Gom các từ thành dòng phụ đề có độ dài xem được.

    Ngắt dòng khi gặp dấu kết câu, khi im lặng đủ lâu, hoặc khi dòng đã quá dài
    hoặc quá lâu. Dấu phẩy chỉ ngắt nếu dòng đã đủ dài, nếu không câu sẽ bị băm
    vụn thành từng mẩu vài chữ.
    """
    lines: List[TranscribedSegment] = []
    buffer: List[_Word] = []

    def flush() -> None:
        if buffer:
            lines.append(TranscribedSegment(
                buffer[0].start, buffer[-1].end,
                " ".join(w.text for w in buffer).strip(),
            ))
            buffer.clear()

    for i, word in enumerate(words):
        buffer.append(word)
        text = "".join(w.text for w in buffer)
        length = len(text)
        duration = buffer[-1].end - buffer[0].start
        gap_ahead = words[i + 1].start - word.end if i + 1 < len(words) else 0.0

        if (word.text.endswith(_SENTENCE_END)
                or gap_ahead >= PAUSE_BREAK_SECONDS
                or length >= MAX_LINE_CHARS
                or duration >= MAX_LINE_SECONDS
                or (word.text.endswith(_SOFT_BREAK) and length >= MIN_CHARS_BEFORE_COMMA_BREAK)):
            flush()

    flush()
    return lines


def transcribe_to_srt(
    audio_path: str,
    output_path: Optional[str] = None,
    model_size: str = DEFAULT_MODEL,
    language: Optional[str] = "vi",
    progress: Optional[ProgressCallback] = None,
) -> str:
    """Nhận dạng rồi ghi thẳng ra file .srt. Trả về đường dẫn file đã ghi.

    Mặc định ghi cạnh file voice để người dùng mở ra sửa lại trước khi dựng
    project - nhận dạng máy bao giờ cũng cần soát lại đôi chỗ.
    """
    segments = transcribe(audio_path, model_size, language, progress)

    if output_path is None:
        output_path = os.path.splitext(audio_path)[0] + ".srt"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(segments_to_srt(segments))
    except OSError as exc:
        raise TranscribeError(f"Không ghi được file SRT: {exc}") from exc

    return output_path
