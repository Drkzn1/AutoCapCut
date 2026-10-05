"""Giao diện AutoCapCut."""

from __future__ import annotations

import os
import sys
import traceback
from typing import Dict, Optional

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import capcut, transcribe
from .builder import BuildRequest, BuildResult, build_project
from .media import SortMode
from .transcribe import DEFAULT_MODEL as DEFAULT_WHISPER_MODEL, MODEL_SIZES
from .motion import MotionConfig, MotionSetting, MotionType
from .settings import load_settings, save_settings

AUDIO_FILTER = "File âm thanh (*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.wma);;Tất cả (*)"
SRT_FILTER = "File phụ đề (*.srt);;Tất cả (*)"
TEXT_FILTER = "File văn bản (*.txt);;Tất cả (*)"

RESOLUTIONS = [
    ("Ngang 1920 x 1080", 1920, 1080),
    ("Dọc 1080 x 1920", 1080, 1920),
    ("Vuông 1080 x 1080", 1080, 1080),
    ("Ngang 1280 x 720", 1280, 720),
    ("Dọc 720 x 1280", 720, 1280),
    ("Ngang 2560 x 1440", 2560, 1440),
    ("Ngang 3840 x 2160", 3840, 2160),
]

STYLESHEET = """
QWidget { background: #23262d; color: #e6e8ec; font-size: 13px; }
QLabel#title { font-size: 22px; font-weight: 600; padding: 14px 0 18px 0; }
QLabel#section { color: #9aa3b2; font-size: 12px; padding-top: 6px; }
QLineEdit, QPlainTextEdit, QComboBox {
    background: #1b1e24; border: 1px solid #333842; border-radius: 6px;
    padding: 7px 10px; selection-background-color: #2f6fd0;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: #2f6fd0; }
QLineEdit:disabled, QComboBox:disabled { color: #6b7280; }
QPushButton {
    background: #2f6fd0; border: none; border-radius: 6px;
    padding: 8px 20px; font-weight: 600;
}
QPushButton:hover { background: #3b7ee0; }
QPushButton:pressed { background: #2559a8; }
QPushButton:disabled { background: #3a3f48; color: #7b8290; }
QPushButton#run { padding: 15px 40px; font-size: 15px; letter-spacing: 1px; }
QCheckBox::indicator {
    width: 17px; height: 17px; border-radius: 4px;
    border: 1px solid #4a505c; background: #1b1e24;
}
QCheckBox::indicator:checked { background: #2f6fd0; border-color: #2f6fd0; }
QCheckBox:disabled { color: #6b7280; }
QFrame#card { background: #262a32; border: 1px solid #313640; border-radius: 10px; }
QTextEdit#log {
    background: #16181d; border: 1px solid #313640; border-radius: 8px;
    font-family: Menlo, Consolas, monospace; font-size: 12px;
}
QProgressBar { background: #1b1e24; border: none; border-radius: 3px; height: 6px; }
QProgressBar::chunk { background: #2f6fd0; border-radius: 3px; }
QComboBox::drop-down { border: none; width: 22px; }
QScrollArea#scroll { background: #23262d; }
QScrollArea#scroll > QWidget > QWidget { background: #23262d; }
QScrollBar:vertical, QScrollBar:horizontal { background: transparent; border: none; }
QScrollBar:vertical { width: 10px; }
QScrollBar:horizontal { height: 10px; }
QScrollBar::handle { background: #414855; border-radius: 5px; min-height: 30px; min-width: 30px; }
QScrollBar::handle:hover { background: #525b6b; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""


class BuildWorker(QObject):
    """Chạy việc dựng draft ở luồng riêng để giao diện không bị treo."""

    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, request: BuildRequest):
        super().__init__()
        self._request = request

    def run(self) -> None:
        try:
            result = build_project(self._request, progress=self.progress.emit)
        except Exception as exc:
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            self.failed.emit(detail)
        else:
            self.finished.emit(result)


class MotionRow:
    """Một dòng thiết lập chuyển động: checkbox + các ô số tương ứng."""

    def __init__(self, motion: MotionType, setting: MotionSetting, grid: QGridLayout,
                 row: int, column: int):
        self.motion = motion
        base = column * 8

        self.checkbox = QCheckBox(motion.value)
        self.checkbox.setChecked(setting.enabled)
        self.checkbox.setMinimumWidth(84)
        grid.addWidget(self.checkbox, row, base)

        self.x_field: Optional[QLineEdit] = None
        self.y_field: Optional[QLineEdit] = None

        self.scale_field = _number_field(setting.scale_percent)

        if motion.is_pan:
            self.x_field = _number_field(setting.amount_x)
            self.y_field = _number_field(setting.amount_y)
            grid.addWidget(QLabel("X"), row, base + 1)
            grid.addWidget(self.x_field, row, base + 2)
            grid.addWidget(QLabel("Y"), row, base + 3)
            grid.addWidget(self.y_field, row, base + 4)
            grid.addWidget(QLabel("Scale"), row, base + 5)
            grid.addWidget(self.scale_field, row, base + 6)
            grid.addWidget(QLabel("%"), row, base + 7)
        else:
            # Zoom không có X/Y nên ô % đứng ngay cạnh nhãn thay vì lùi ra tận
            # cột Scale, tránh khoảng trống rỗng giữa dòng
            grid.addWidget(self.scale_field, row, base + 1, 1, 2)
            grid.addWidget(QLabel("%"), row, base + 3)

        self.checkbox.toggled.connect(self._sync_enabled)
        self._sync_enabled(self.checkbox.isChecked())

    def _sync_enabled(self, enabled: bool) -> None:
        for field in (self.x_field, self.y_field, self.scale_field):
            if field is not None:
                field.setEnabled(enabled)

    def to_setting(self) -> MotionSetting:
        return MotionSetting(
            enabled=self.checkbox.isChecked(),
            scale_percent=_read_number(self.scale_field, 110.0),
            amount_x=_read_number(self.x_field, 0.0),
            amount_y=_read_number(self.y_field, 0.0),
        )

    def apply(self, setting: MotionSetting) -> None:
        self.checkbox.setChecked(setting.enabled)
        self.scale_field.setText(_format_number(setting.scale_percent))
        if self.x_field is not None:
            self.x_field.setText(_format_number(setting.amount_x))
        if self.y_field is not None:
            self.y_field.setText(_format_number(setting.amount_y))


def _number_field(value: float) -> QLineEdit:
    field = QLineEdit(_format_number(value))
    field.setFixedWidth(58)
    field.setAlignment(Qt.AlignCenter)
    return field


def _compact(combo: QComboBox, characters: int = 12) -> QComboBox:
    """Cho combo co lại thay vì bám theo chiều dài mục dài nhất.

    Mặc định Qt lấy chiều rộng đúng bằng mục dài nhất, khiến cả hàng không thu
    nhỏ được và người dùng phải cuộn ngang khi để cửa sổ hẹp.
    """
    combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(characters)
    return combo


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _read_number(field: Optional[QLineEdit], fallback: float) -> float:
    if field is None:
        return fallback
    try:
        return float(field.text().strip().replace(",", "."))
    except ValueError:
        return fallback


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoCapCut - Tự động khớp media và âm thanh")
        # Nhỏ vừa đủ để lọt màn hình laptop 13"; nhỏ hơn nữa thì vùng cuộn lo
        self.setMinimumSize(720, 480)
        self.resize(1060, 940)
        self.setStyleSheet(STYLESHEET)

        self._thread: Optional[QThread] = None
        self._worker: Optional[BuildWorker] = None
        self._motion_rows: Dict[MotionType, MotionRow] = {}

        self._build_ui()
        self._restore_settings()

    # ------------------------------------------------------------------ giao diện

    def _build_ui(self) -> None:
        # Toàn bộ nội dung nằm trong vùng cuộn. Không có nó, khi người dùng thu
        # cửa sổ thấp hơn chiều cao tối thiểu của layout, Qt ép các widget lại
        # và chúng đè lên nhau thay vì cho cuộn.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addWidget(scroll)

        page = QWidget()
        scroll.setWidget(page)

        root = QVBoxLayout(page)
        root.setContentsMargins(28, 18, 28, 22)
        root.setSpacing(12)

        title = QLabel("Tự động khớp ảnh/video và âm thanh")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        root.addLayout(self._build_inputs())
        root.addWidget(self._build_options())
        root.addWidget(self._build_motion())

        self.run_button = QPushButton("TẠO PROJECT CAPCUT")
        self.run_button.setObjectName("run")
        self.run_button.clicked.connect(self._on_run)
        run_row = QHBoxLayout()
        run_row.addStretch()
        run_row.addWidget(self.run_button)
        run_row.addStretch()
        root.addSpacing(6)
        root.addLayout(run_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        root.addWidget(self.progress_bar)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.log_view, stretch=1)

    def _build_inputs(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        self.audio_field = QLineEdit()
        self.audio_field.setPlaceholderText("Chọn file audio")
        self._add_row(grid, 0, "File voice:", self.audio_field,
                      lambda: self._pick_file(self.audio_field, "Chọn file voice", AUDIO_FILTER))

        self.srt_field = QLineEdit()
        self.srt_field.setPlaceholderText("Chọn file SRT")
        self._add_row(grid, 1, "File SRT:", self.srt_field,
                      lambda: self._pick_file(self.srt_field, "Chọn file SRT", SRT_FILTER))

        grid.addLayout(self._build_auto_srt_row(), 2, 1, 1, 2)

        grid.addWidget(QLabel("Danh sách scene:"), 3, 0, Qt.AlignTop)
        self.scenes_field = QPlainTextEdit()
        self.scenes_field.setPlaceholderText(
            "Mỗi scene một dòng. Ví dụ:\n1. Chó chạy\n2. Mèo chạy\n\n"
            "Để trống nếu muốn tool tự chia đều phụ đề cho số file media."
        )
        self.scenes_field.setMinimumHeight(110)
        grid.addWidget(self.scenes_field, 3, 1)
        scenes_browse = QPushButton("Chọn file")
        scenes_browse.clicked.connect(self._pick_scenes_file)
        scenes_box = QVBoxLayout()
        scenes_box.addWidget(scenes_browse)
        scenes_box.addStretch()
        grid.addLayout(scenes_box, 3, 2)

        self.media_field = QLineEdit()
        self.media_field.setPlaceholderText("Chọn thư mục chứa ảnh hoặc video")
        self._add_row(grid, 4, "Thư mục media:", self.media_field,
                      self._pick_media_folder, button_text="Chọn thư mục")

        self.name_field = QLineEdit()
        self.name_field.setPlaceholderText("Đặt tên cho dự án CapCut")
        grid.addWidget(QLabel("Tên project:"), 5, 0)
        grid.addWidget(self.name_field, 5, 1, 1, 2)

        self.draft_field = QLineEdit()
        self.draft_field.setPlaceholderText("Tự động dò tìm")
        self._add_row(grid, 6, "Thư mục draft:", self.draft_field,
                      self._pick_draft_folder, button_text="Chọn thư mục")

        return grid

    def _build_auto_srt_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)

        self.auto_srt_checkbox = QCheckBox("Không có SRT? Tự tạo từ file voice")
        self.auto_srt_checkbox.toggled.connect(self._sync_auto_srt)
        row.addWidget(self.auto_srt_checkbox)
        row.addSpacing(12)

        self.model_combo = _compact(QComboBox(), 12)
        for size in MODEL_SIZES:
            label = size + ("  (nhanh, kém chuẩn)" if size in ("tiny", "base")
                            else "  (chậm, chuẩn nhất)" if size == "large-v3" else "")
            self.model_combo.addItem(label, size)
        self.model_combo.setCurrentIndex(MODEL_SIZES.index(DEFAULT_WHISPER_MODEL))
        row.addWidget(self.model_combo)

        self.language_combo = _compact(QComboBox(), 10)
        for label, code in [("Tiếng Việt", "vi"), ("English", "en"), ("Tự nhận biết", "")]:
            self.language_combo.addItem(label, code)
        row.addWidget(self.language_combo)

        if not transcribe.is_available():
            self.auto_srt_checkbox.setEnabled(False)
            # Trong bản .app đã đóng gói thì không pip install được, nên phải chỉ
            # đúng cách khắc phục thay vì đưa lệnh vô dụng
            self.auto_srt_checkbox.setText(
                "Tự tạo SRT: bản gọn không kèm - hãy chọn file SRT có sẵn"
                if getattr(sys, "frozen", False) else
                "Tự tạo SRT (cần cài: pip install faster-whisper)"
            )

        row.addStretch()
        self._sync_auto_srt(False)
        return row

    def _sync_auto_srt(self, enabled: bool) -> None:
        """Bật tự nhận dạng thì khoá ô SRT lại, tránh người dùng tưởng phải điền cả hai."""
        self.model_combo.setEnabled(enabled)
        self.language_combo.setEnabled(enabled)
        self.srt_field.setEnabled(not enabled)
        self.srt_field.setPlaceholderText(
            "Sẽ tự tạo từ file voice" if enabled else "Chọn file SRT"
        )

    def _add_row(self, grid: QGridLayout, row: int, label: str, field: QLineEdit,
                 handler, button_text: str = "Chọn file") -> None:
        grid.addWidget(QLabel(label), row, 0)
        grid.addWidget(field, row, 1)
        button = QPushButton(button_text)
        button.clicked.connect(handler)
        grid.addWidget(button, row, 2)

    def _build_options(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        self.subtitle_checkbox = QCheckBox("Tự động chèn phụ đề vào video")
        self.subtitle_checkbox.setChecked(True)
        layout.addWidget(self.subtitle_checkbox)

        self.mute_checkbox = QCheckBox("Tắt tiếng gốc của video")
        self.mute_checkbox.setChecked(True)
        layout.addWidget(self.mute_checkbox)
        layout.addStretch()

        layout.addWidget(QLabel("Khung hình:"))
        self.resolution_combo = _compact(QComboBox(), 14)
        for label, _w, _h in RESOLUTIONS:
            self.resolution_combo.addItem(label)
        layout.addWidget(self.resolution_combo)

        self.sort_combo = _compact(QComboBox(), 16)
        for mode in SortMode:
            self.sort_combo.addItem(mode.value, mode)
        layout.addWidget(self.sort_combo)
        return card

    def _build_motion(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 12, 16, 14)
        outer.setSpacing(10)

        header = QHBoxLayout()
        self.motion_checkbox = QCheckBox("Auto keyframe chuyển động cho ảnh/video")
        self.motion_checkbox.setChecked(True)
        self.motion_checkbox.toggled.connect(self._sync_motion_enabled)
        header.addWidget(self.motion_checkbox)
        header.addStretch()
        self.shuffle_checkbox = QCheckBox("Trộn ngẫu nhiên các kiểu đã chọn")
        self.shuffle_checkbox.setChecked(True)
        header.addWidget(self.shuffle_checkbox)
        outer.addLayout(header)

        self.motion_grid = QGridLayout()
        self.motion_grid.setHorizontalSpacing(5)
        self.motion_grid.setVerticalSpacing(9)
        defaults = MotionConfig.default().settings

        pairs = [
            (MotionType.ZOOM_IN, MotionType.ZOOM_OUT),
            (MotionType.PAN_UP, MotionType.PAN_DOWN),
            (MotionType.PAN_LEFT, MotionType.PAN_RIGHT),
        ]
        for row, (left, right) in enumerate(pairs):
            self._motion_rows[left] = MotionRow(left, defaults[left], self.motion_grid, row, 0)
            self._motion_rows[right] = MotionRow(right, defaults[right], self.motion_grid, row, 1)
        self.motion_grid.setColumnStretch(7, 1)
        self.motion_grid.setColumnStretch(15, 1)
        outer.addLayout(self.motion_grid)

        hint = QLabel(
            "Gợi ý: biên độ pan tối đa an toàn = (Scale − 100%) × cạnh khung hình. "
            "Vượt quá sẽ bị tool tự cắt bớt để không lộ viền đen."
        )
        hint.setObjectName("section")
        hint.setWordWrap(True)
        outer.addWidget(hint)
        return card

    def _sync_motion_enabled(self, enabled: bool) -> None:
        self.shuffle_checkbox.setEnabled(enabled)
        for row in self._motion_rows.values():
            row.checkbox.setEnabled(enabled)
            row._sync_enabled(enabled and row.checkbox.isChecked())

    # ------------------------------------------------------------------ chọn file

    def _pick_file(self, field: QLineEdit, caption: str, file_filter: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, caption, field.text() or os.path.expanduser("~"),
                                              file_filter)
        if path:
            field.setText(path)
            self._autofill_name(path)

    def _pick_scenes_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file danh sách scene",
                                              os.path.expanduser("~"), TEXT_FILTER)
        if not path:
            return
        for encoding in ("utf-8-sig", "utf-8", "cp1258", "latin-1"):
            try:
                with open(path, "r", encoding=encoding) as f:
                    self.scenes_field.setPlainText(f.read())
                return
            except UnicodeDecodeError:
                continue
        QMessageBox.warning(self, "Không đọc được file", f"Không giải mã được nội dung {path}")

    def _pick_media_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục ảnh/video",
                                                self.media_field.text() or os.path.expanduser("~"))
        if path:
            self.media_field.setText(path)

    def _pick_draft_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chọn thư mục draft của CapCut",
                                                self.draft_field.text() or os.path.expanduser("~"))
        if path:
            self.draft_field.setText(path)

    def _autofill_name(self, path: str) -> None:
        """Lấy tên file voice làm tên project để đỡ phải gõ."""
        if not self.name_field.text().strip():
            self.name_field.setText(os.path.splitext(os.path.basename(path))[0])

    # ------------------------------------------------------------------ chạy

    def _collect_request(self) -> BuildRequest:
        _label, width, height = RESOLUTIONS[self.resolution_combo.currentIndex()]
        motion = MotionConfig(
            enabled=self.motion_checkbox.isChecked(),
            shuffle=self.shuffle_checkbox.isChecked(),
            settings={m: row.to_setting() for m, row in self._motion_rows.items()},
        )
        return BuildRequest(
            audio_path=self.audio_field.text().strip(),
            srt_path="" if self.auto_srt_checkbox.isChecked() else self.srt_field.text().strip(),
            auto_srt=self.auto_srt_checkbox.isChecked(),
            whisper_model=self.model_combo.currentData(),
            language=self.language_combo.currentData() or None,
            scenes_text=self.scenes_field.toPlainText(),
            media_folder=self.media_field.text().strip(),
            draft_name=self.name_field.text().strip(),
            draft_folder=self.draft_field.text().strip() or None,
            width=width,
            height=height,
            burn_subtitles=self.subtitle_checkbox.isChecked(),
            mute_source_video=self.mute_checkbox.isChecked(),
            sort_mode=self.sort_combo.currentData(),
            motion=motion,
        )

    def _on_run(self) -> None:
        if self._thread is not None:
            return
        self.log_view.clear()
        request = self._collect_request()
        self._save_settings(request)

        self.run_button.setEnabled(False)
        self.progress_bar.setVisible(True)

        self._thread = QThread(self)
        self._worker = BuildWorker(request)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._log)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _teardown_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
        self._worker = None
        self.run_button.setEnabled(True)
        self.progress_bar.setVisible(False)

    def _on_finished(self, result: BuildResult) -> None:
        self._teardown_thread()
        self._log("")
        self._log(f"XONG - đã tạo project \"{result.draft_name}\"")
        self._log(f"  {result.scene_count} scene · {result.media_count} file media "
                  f"· dài {result.duration / 1_000_000:.1f} giây")
        self._log(f"  {result.draft_path}")
        if result.srt_path and result.srt_path != self.srt_field.text().strip():
            self.srt_field.setText(result.srt_path)
        for warning in result.warnings:
            self._log(f"  [Lưu ý] {warning}")
        self._log("")
        self._log("Mở CapCut là thấy project trong danh sách dự án.")

    def _on_failed(self, message: str) -> None:
        self._teardown_thread()
        self._log(f"LỖI: {message}")
        QMessageBox.critical(self, "Không tạo được project", message)

    def _log(self, message: str) -> None:
        self.log_view.append(message)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    # ------------------------------------------------------------------ ghi nhớ

    def _restore_settings(self) -> None:
        data = load_settings()
        if not data:
            self.draft_field.setText(capcut.find_draft_folder() or "")
            return

        self.audio_field.setText(data.get("audio_path", ""))
        self.srt_field.setText(data.get("srt_path", ""))
        self.media_field.setText(data.get("media_folder", ""))
        self.draft_field.setText(data.get("draft_folder") or capcut.find_draft_folder() or "")
        self.subtitle_checkbox.setChecked(data.get("burn_subtitles", True))
        self.mute_checkbox.setChecked(data.get("mute_source_video", True))
        self.resolution_combo.setCurrentIndex(data.get("resolution_index", 0))

        if transcribe.is_available():
            self.auto_srt_checkbox.setChecked(data.get("auto_srt", False))
        model = data.get("whisper_model", DEFAULT_WHISPER_MODEL)
        if model in MODEL_SIZES:
            self.model_combo.setCurrentIndex(MODEL_SIZES.index(model))
        language = data.get("language", "vi")
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == language:
                self.language_combo.setCurrentIndex(i)
                break

        sort_value = data.get("sort_mode")
        for i, mode in enumerate(SortMode):
            if mode.name == sort_value:
                self.sort_combo.setCurrentIndex(i)

        motion = data.get("motion", {})
        self.motion_checkbox.setChecked(motion.get("enabled", True))
        self.shuffle_checkbox.setChecked(motion.get("shuffle", True))
        for name, values in motion.get("settings", {}).items():
            try:
                row = self._motion_rows[MotionType[name]]
            except KeyError:
                continue
            row.apply(MotionSetting(**values))
        self._sync_motion_enabled(self.motion_checkbox.isChecked())

    def _save_settings(self, request: BuildRequest) -> None:
        save_settings({
            "audio_path": request.audio_path,
            "srt_path": request.srt_path,
            "media_folder": request.media_folder,
            "draft_folder": request.draft_folder or "",
            "burn_subtitles": request.burn_subtitles,
            "mute_source_video": request.mute_source_video,
            "auto_srt": request.auto_srt,
            "whisper_model": request.whisper_model,
            "language": request.language or "",
            "resolution_index": self.resolution_combo.currentIndex(),
            "sort_mode": request.sort_mode.name,
            "motion": {
                "enabled": request.motion.enabled,
                "shuffle": request.motion.shuffle,
                "settings": {
                    m.name: {
                        "enabled": s.enabled,
                        "scale_percent": s.scale_percent,
                        "amount_x": s.amount_x,
                        "amount_y": s.amount_y,
                    }
                    for m, s in request.motion.settings.items()
                },
            },
        })

    def closeEvent(self, event) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
        super().closeEvent(event)


def run() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("AutoCapCut")
    window = MainWindow()
    window.show()
    return app.exec()
