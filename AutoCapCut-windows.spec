# -*- mode: python ; coding: utf-8 -*-
"""Đóng gói AutoCapCut thành .exe cho Windows (bản gọn, không kèm Whisper).

PHẢI chạy trên máy Windows - PyInstaller không build chéo hệ điều hành được.
Chạy: build_windows.bat  (hoặc: pyinstaller AutoCapCut-windows.spec --noconfirm)
"""

from PyInstaller.utils.hooks import collect_data_files

# Hai thư viện này tra file theo __file__ nên phải giữ nguyên vị trí tương đối.
# Trên Windows pymediainfo mang theo MediaInfo.dll thay cho .dylib của macOS.
datas = []
datas += collect_data_files("pycapcut", includes=["assets/*.json"])
datas += collect_data_files("pymediainfo", includes=["*.dll"])

WHISPER_STACK = [
    "faster_whisper", "ctranslate2", "onnxruntime", "av", "tokenizers",
    "torch", "torchaudio", "transformers", "huggingface_hub", "datasets",
]

UNUSED = [
    "tkinter", "test", "unittest", "pydoc", "doctest", "lib2to3",
    "matplotlib", "scipy", "pandas", "IPython", "notebook",
    "setuptools", "pip", "wheel", "PyInstaller",
]

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
    name="AutoCapCut Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # không hiện cửa sổ đen khi bấm đúp
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="build/AutoCapCut.ico",
)

# Xuất ra một thư mục thay vì gộp thành file .exe đơn lẻ: khởi động nhanh hơn
# nhiều và Windows Defender ít nghi ngờ hơn so với bản one-file tự giải nén.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AutoCapCut Studio",
)
