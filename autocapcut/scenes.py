"""Khớp danh sách scene với mốc thời gian lấy từ SRT.

Bài toán: người dùng đưa N scene (mỗi dòng một câu, viết theo kịch bản gốc) và
một file SRT do công cụ nhận dạng giọng nói sinh ra. SRT hầu như không bao giờ
cắt câu giống hệt kịch bản - nó gộp câu, tách câu, sai chính tả. Vì vậy không
thể ghép cứng theo chỉ số mà phải căn theo nội dung.

Cách làm: đưa cả hai bên về chuỗi từ đã chuẩn hoá, dùng SequenceMatcher tìm các
đoạn trùng nhau, rồi suy ra từ đầu tiên của mỗi scene rơi vào block SRT nào.
Mốc bắt đầu của scene = mốc bắt đầu của block đó.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .srt import SrtBlock

# "1. Chó chạy", "1) Chó chạy", "- Chó chạy", "Scene 1: Chó chạy"
_LEADING_NUMBER = re.compile(
    r"^\s*(?:scene|cảnh|canh)?\s*\d+\s*[\.\)\:\-–]\s*|^\s*[-*•]\s*",
    re.IGNORECASE,
)
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


class AlignmentError(ValueError):
    pass


@dataclass
class Scene:
    index: int
    """số thứ tự bắt đầu từ 1"""
    text: str
    start: int = 0
    """micro giây"""
    end: int = 0
    """micro giây"""

    @property
    def duration(self) -> int:
        return self.end - self.start


def parse_scenes(raw: str) -> List[Scene]:
    """Mỗi dòng không rỗng là một scene. Tự bỏ số thứ tự ở đầu dòng nếu có."""
    scenes: List[Scene] = []
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _LEADING_NUMBER.sub("", line).strip()
        if line:
            scenes.append(Scene(len(scenes) + 1, line))
    return scenes


def read_scenes_file(path: str) -> List[Scene]:
    for encoding in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return parse_scenes(f.read())
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Không giải mã được file scene: {path}")


def _normalize(text: str) -> str:
    """Bỏ dấu, bỏ ký tự đặc biệt, về chữ thường.

    Bỏ dấu tiếng Việt là cố ý: SRT sinh tự động rất hay sai dấu, so sánh phần
    chữ cái trần cho tỷ lệ khớp cao hơn hẳn.
    """
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d")
    return _PUNCT.sub(" ", text)


def _tokenize(text: str) -> List[str]:
    return _normalize(text).split()


def align_scenes_to_srt(
    scenes: Sequence[Scene],
    blocks: Sequence[SrtBlock],
    total_duration: Optional[int] = None,
) -> List[Scene]:
    """Gán start/end cho từng scene. Trả về danh sách scene mới, không sửa input.

    Args:
        scenes: danh sách scene theo đúng thứ tự xuất hiện trong video.
        blocks: các block SRT đã sắp xếp theo thời gian.
        total_duration: độ dài file voice (micro giây). Scene cuối sẽ kéo dài
            tới đây để không bị hụt hình ở cuối video.
    """
    if not scenes:
        raise AlignmentError("Danh sách scene đang trống.")
    if not blocks:
        raise AlignmentError("File SRT không có block nào hợp lệ.")

    timeline_end = max(total_duration or 0, blocks[-1].end)
    result = [Scene(s.index, s.text) for s in scenes]

    starts = _match_by_content(result, blocks)
    if starts is None:
        starts = _match_by_proportion(len(result), blocks)
    starts = _spread_duplicates(starts, timeline_end)

    for i, scene in enumerate(result):
        scene.start = starts[i]
        scene.end = starts[i + 1] if i + 1 < len(starts) else timeline_end

    # Scene rỗng thời lượng (do hai scene khớp cùng một block) được cấp tối thiểu
    # 1 frame ở 30fps để CapCut không bỏ qua segment.
    _enforce_minimum_duration(result, timeline_end, minimum=33_333)
    return result


def _match_by_content(
    scenes: Sequence[Scene], blocks: Sequence[SrtBlock]
) -> Optional[List[int]]:
    """Trả về mốc bắt đầu của từng scene, hoặc None nếu nội dung quá khác nhau."""
    # Chuỗi từ của SRT, kèm bản đồ vị trí từ -> block chứa nó
    srt_tokens: List[str] = []
    token_to_block: List[int] = []
    for bi, block in enumerate(blocks):
        for token in _tokenize(block.text):
            srt_tokens.append(token)
            token_to_block.append(bi)

    # Chuỗi từ của scene, kèm bản đồ vị trí từ -> scene chứa nó
    scene_tokens: List[str] = []
    token_to_scene: List[int] = []
    for si, scene in enumerate(scenes):
        for token in _tokenize(scene.text):
            scene_tokens.append(token)
            token_to_scene.append(si)

    if not srt_tokens or not scene_tokens:
        return None

    matcher = difflib.SequenceMatcher(None, srt_tokens, scene_tokens, autojunk=False)

    # Với mỗi scene, giữ vị trí từ SRT nhỏ nhất đã khớp được
    first_srt_token: List[Optional[int]] = [None] * len(scenes)
    matched_tokens = 0
    for srt_pos, scene_pos, size in matcher.get_matching_blocks():
        if size == 0:
            continue
        matched_tokens += size
        for offset in range(size):
            si = token_to_scene[scene_pos + offset]
            candidate = srt_pos + offset
            if first_srt_token[si] is None or candidate < first_srt_token[si]:
                first_srt_token[si] = candidate

    # Khớp quá ít nghĩa là scene và SRT không cùng nội dung -> để caller fallback
    if matched_tokens / len(scene_tokens) < 0.35:
        return None

    starts: List[Optional[int]] = [
        blocks[token_to_block[pos]].start if pos is not None else None
        for pos in first_srt_token
    ]
    return _repair_monotonic(starts, blocks)


def _repair_monotonic(
    starts: Sequence[Optional[int]], blocks: Sequence[SrtBlock]
) -> List[int]:
    """Điền chỗ trống và ép dãy mốc thời gian tăng dần.

    Scene không khớp được từ nào (ví dụ mô tả hình ảnh chứ không phải lời thoại)
    sẽ được nội suy đều giữa hai scene khớp gần nhất.
    """
    fixed: List[Optional[int]] = list(starts)

    # Ép tăng dần: mốc lùi về sau bị coi là khớp sai, xoá đi để nội suy lại
    last = -1
    for i, value in enumerate(fixed):
        if value is None:
            continue
        if value < last:
            fixed[i] = None
        else:
            last = value

    known = [i for i, v in enumerate(fixed) if v is not None]
    if not known:
        return _match_by_proportion(len(fixed), blocks)

    # Trước mốc khớp đầu tiên và sau mốc khớp cuối cùng
    for i in range(known[0]):
        fixed[i] = blocks[0].start
    for i in range(known[-1] + 1, len(fixed)):
        fixed[i] = fixed[known[-1]]

    # Nội suy tuyến tính các khoảng trống ở giữa
    for a, b in zip(known, known[1:]):
        gap = b - a
        if gap <= 1:
            continue
        left, right = fixed[a], fixed[b]
        step = (right - left) / gap
        for k in range(1, gap):
            fixed[a + k] = int(left + step * k)

    return [int(v) for v in fixed]  # type: ignore[arg-type]


def _spread_duplicates(starts: Sequence[int], timeline_end: int) -> List[int]:
    """Chia đều các scene rơi trúng cùng một mốc thời gian.

    Nhiều scene khớp về cùng một block SRT là chuyện thường: kịch bản tách câu
    nhỏ hơn lời đọc, hoặc scene chỉ mô tả hình ảnh nên không có chữ nào để khớp.
    Nếu để nguyên, chúng sẽ chồng lên nhau và bị cắt còn đúng một frame - xem ra
    video là những cú nháy hình. Trải đều trong khoảng tới mốc kế tiếp thì mỗi
    scene vẫn được một lát thời gian xem được.
    """
    result = list(starts)
    i = 0
    while i < len(result):
        j = i
        while j + 1 < len(result) and result[j + 1] == result[i]:
            j += 1

        run_length = j - i + 1
        if run_length > 1:
            begin = result[i]
            end = result[j + 1] if j + 1 < len(result) else timeline_end
            if end > begin:
                step = (end - begin) / run_length
                for k in range(1, run_length):
                    result[i + k] = int(begin + step * k)
        i = j + 1
    return result


def _match_by_proportion(count: int, blocks: Sequence[SrtBlock]) -> List[int]:
    """Chia đều số block SRT cho số scene - dùng khi không khớp được nội dung.

    Cố tình trả về mốc trùng nhau khi số scene nhiều hơn số câu phụ đề;
    `_spread_duplicates` sẽ trải chúng ra sau. Nếu đẩy lệch ngay tại đây thì các
    scene thừa chỉ được vài phần nghìn giây.
    """
    return [
        blocks[min(len(blocks) - 1, i * len(blocks) // count)].start
        for i in range(count)
    ]


def _enforce_minimum_duration(scenes: List[Scene], timeline_end: int, minimum: int) -> None:
    for i, scene in enumerate(scenes):
        if scene.duration >= minimum:
            continue
        scene.end = scene.start + minimum
        # Đẩy các scene phía sau để không chồng lấn
        for later in scenes[i + 1:]:
            if later.start >= scene.end:
                break
            shift = scene.end - later.start
            later.start += shift
            later.end = max(later.end + shift, later.start + minimum)
    if scenes:
        scenes[-1].end = max(scenes[-1].end, timeline_end)
