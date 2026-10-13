"""Генерирует assets/icon.ico для сборки EXE (вызывается из build.bat)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from prosetup.ui.icon import draw_icon  # noqa: E402


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841 — нужен для QPixmap
    out = ROOT / "assets" / "icon.ico"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not draw_icon(256).save(str(out), "ICO"):
        # запасной вариант — PNG, PyInstaller 6 сам конвертирует его через Pillow
        print("ICO is not supported by this Qt build, saved PNG instead", file=sys.stderr)
        draw_icon(256).save(str(out.with_suffix(".png")), "PNG")
        return 2
    print(f"Icon saved: {out}")  # ASCII: консоль Windows может быть не в UTF-8
    return 0


if __name__ == "__main__":
    sys.exit(main())
