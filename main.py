#!/usr/bin/env python3
"""AutoCapCut - mở giao diện, hoặc chạy bằng dòng lệnh nếu có tham số."""

import os
import sys


def _ensure_streams() -> None:
    """Bảo đảm stdout/stderr luôn tồn tại.

    App đóng gói ở chế độ cửa sổ trên Windows không có console, khi đó Python
    đặt sys.stdout = None. Mọi lệnh print() sau đó sẽ ném AttributeError và làm
    chết chế độ dòng lệnh. Nối vào hố đen còn hơn để nó sập.
    """
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def main() -> int:
    _ensure_streams()

    if len(sys.argv) > 1:
        from autocapcut.cli import main as cli_main
        return cli_main(sys.argv[1:])

    from autocapcut.gui import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
