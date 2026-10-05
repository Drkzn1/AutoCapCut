# -*- mode: python ; coding: utf-8 -*-
"""Đóng gói AutoCapCut thành .app cho macOS (bản gọn, không kèm Whisper).

Chạy: .venv/bin/pyinstaller AutoCapCut.spec --noconfirm

Bản này bỏ phần nhận dạng giọng nói. `transcribe.py` vẫn nằm trong app nhưng
`is_available()` sẽ trả về False, giao diện tự khoá ô "Tự tạo SRT" lại và ghi rõ
lý do - nên app không vỡ, chỉ mất tính năng đó.
"""

import os

from PyInstaller.utils.hooks import collect_data_files

SITE = os.path.join("..venv", "lib")  # chỉ để tài liệu, đường dẫn thật lấy từ hook

# Hai thư viện dưới đây tra file theo __file__ nên phải giữ nguyên vị trí tương
# đối trong package, không gộp chung vào thư mục gốc được.
datas = []
datas += collect_data_files("pycapcut", includes=["assets/*.json"])
datas += collect_data_files("pymediainfo", includes=["*.dylib"])

# Whisper và toàn bộ dây chuyền suy luận của nó - chiếm phần lớn dung lượng
WHISPER_STACK = [
    "faster_whisper", "ctranslate2", "onnxruntime", "av", "tokenizers",
    "torch", "torchaudio", "transformers", "huggingface_hub", "datasets",
]

# Các thứ PyInstaller hay kéo theo mà app không đụng tới
UNUSED = [
    "tkinter", "test", "unittest", "pydoc", "doctest", "lib2to3",
    "matplotlib", "scipy", "pandas", "IPython", "notebook",
    "setuptools", "pip", "wheel", "PyInstaller",
]

# Module Qt không dùng. PySide6 rất nặng, bỏ được cái nào hay cái đó.
UNUSED_QT = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets", "PySide6.QtQml",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtBluetooth",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSerialPort",
    "PySide6.QtNetworkAuth", "PySide6.QtRemoteObjects", "PySide6.QtSensors",
    "PySide6.QtSpatialAudio", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSvgWidgets",
    "PySide6.QtScxml", "PySide6.QtStateMachine", "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtNfc",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["pycapcut", "pymediainfo"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=WHISPER_STACK + UNUSED + UNUSED_QT,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoCapCut",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # không hiện cửa sổ Terminal khi bấm đúp
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AutoCapCut",
)

app = BUNDLE(
    coll,
    name="AutoCapCut Studio.app",
    icon="build/AutoCapCut.icns",
    bundle_identifier="com.hoangnguyen.autocapcut",
    version="1.0.0",
    info_plist={
        "CFBundleName": "AutoCapCut Studio",
        "CFBundleDisplayName": "AutoCapCut Studio",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        # App đọc file voice/ảnh người dùng chọn và ghi draft vào thư mục CapCut,
        # macOS sẽ hỏi quyền khi lần đầu chạm vào các thư mục được bảo vệ
        "NSDesktopFolderUsageDescription":
            "AutoCapCut cần đọc file voice và thư mục ảnh bạn chọn trên Desktop.",
        "NSDocumentsFolderUsageDescription":
            "AutoCapCut cần đọc file voice và thư mục ảnh bạn chọn trong Documents.",
        "NSDownloadsFolderUsageDescription":
            "AutoCapCut cần đọc file voice và thư mục ảnh bạn chọn trong Downloads.",
        "NSRemovableVolumesUsageDescription":
            "AutoCapCut cần đọc media bạn chọn từ ổ đĩa ngoài.",
    },
)
