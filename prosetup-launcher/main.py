"""Запуск ProSetup Launcher: python main.py  (или --minimized, чтобы стартовать в трее)."""

import sys

from prosetup.app import run

if __name__ == "__main__":
    sys.exit(run())
