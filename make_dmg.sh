#!/bin/bash
# Đóng gói app thành file .dmg để gửi cho người khác.
# Chạy: ./make_dmg.sh
set -e

cd "$(dirname "$0")"

APP="dist/AutoCapCut Studio.app"
VOLUME="AutoCapCut Studio"
STAGE="build/dmg-stage"
OUT="dist/AutoCapCut-Studio-1.0.0.dmg"

[ -d "$APP" ] || { echo "Chưa có $APP - chạy pyinstaller trước."; exit 1; }

rm -rf "$STAGE" "$OUT"
mkdir -p "$STAGE"

cp -R "$APP" "$STAGE/"
# Lối tắt để người nhận kéo thả app vào Applications ngay trong cửa sổ dmg
ln -s /Applications "$STAGE/Applications"
cp "docs/HUONG DAN CAI DAT.txt" "$STAGE/" 2>/dev/null || true

hdiutil create -volname "$VOLUME" -srcfolder "$STAGE" -ov -format UDZO "$OUT" >/dev/null

rm -rf "$STAGE"
echo "Đã tạo: $OUT"
du -sh "$OUT"
