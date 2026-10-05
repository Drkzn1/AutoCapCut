@echo off
REM ============================================================
REM  Build AutoCapCut Studio thanh .exe cho Windows
REM  Chay file nay TREN MAY WINDOWS (bam dup, hoac go trong cmd)
REM  Yeu cau: da cai Python 3.9 - 3.12 va tick "Add to PATH"
REM ============================================================
setlocal
cd /d "%~dp0"
chcp 65001 >nul

echo.
echo === [1/4] Kiem tra Python ===
where python >nul 2>&1
if errorlevel 1 (
    echo LOI: Khong tim thay Python.
    echo Tai tai https://www.python.org/downloads/ va nho tick "Add python.exe to PATH".
    pause
    exit /b 1
)
python --version

echo.
echo === [2/4] Tao moi truong ao ===
if not exist ".venv-win" (
    python -m venv .venv-win
    if errorlevel 1 ( echo LOI: khong tao duoc venv. & pause & exit /b 1 )
)

echo.
echo === [3/4] Cai thu vien (lan dau se lau vai phut) ===
call .venv-win\Scripts\python.exe -m pip install --upgrade pip
call .venv-win\Scripts\python.exe -m pip install pycapcut PySide6 pyinstaller
if errorlevel 1 ( echo LOI: cai thu vien that bai. & pause & exit /b 1 )

echo.
echo === [4/4] Dong goi ===
call .venv-win\Scripts\pyinstaller.exe AutoCapCut-windows.spec --noconfirm --distpath dist-win --workpath build\work-win
if errorlevel 1 ( echo LOI: dong goi that bai. & pause & exit /b 1 )

echo.
echo ============================================================
echo  XONG!
echo  App nam trong:  dist-win\AutoCapCut Studio\
echo  File chay:      dist-win\AutoCapCut Studio\AutoCapCut Studio.exe
echo.
echo  De gui cho nguoi khac: nen ca thu muc "AutoCapCut Studio"
echo  thanh file .zip roi gui.
echo ============================================================
echo.
pause
