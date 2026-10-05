#!/bin/bash
# Mở AutoCapCut. Truyền tham số vào thì chạy chế độ dòng lệnh.
cd "$(dirname "$0")" || exit 1
exec .venv/bin/python main.py "$@"
