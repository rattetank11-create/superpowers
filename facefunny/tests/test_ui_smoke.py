"""Headless smoke test of the full UI flow (runs with QT_QPA_PLATFORM=offscreen)."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except Exception:  # pragma: no cover - PySide6 missing
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class UiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import theme
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(theme.stylesheet())

    def test_connect_then_f9_f10(self):
        from app.main_window import MainWindow
        from app.simulation import SimState

        w = MainWindow()
        w.show()
        QTest.qWait(100)
        QTest.keyClick(w.connect_screen.input, Qt.Key.Key_Return)  # empty -> stays
        self.assertIs(w.stack.currentWidget(), w.connect_screen)

        QTest.keyClicks(w.connect_screen.input, "connect 127.0.0.1:27015")
        QTest.keyClick(w.connect_screen.input, Qt.Key.Key_Return)
        QTest.qWait(2000)
        self.assertIs(w.stack.currentWidget(), w.radar_screen)
        sim = w.radar_screen.sim

        QTest.keyClick(w, Qt.Key.Key_F9)
        self.assertIs(sim.state, SimState.RUNNING)
        QTest.qWait(500)
        QTest.keyClick(w, Qt.Key.Key_F9)
        self.assertIs(sim.state, SimState.PAUSED)
        w.radar_screen.pause_btn.click()
        self.assertIs(sim.state, SimState.RUNNING)
        QTest.keyClick(w, Qt.Key.Key_F10)
        self.assertIs(sim.state, SimState.IDLE)
        w.radar_screen.reset_btn.click()
        self.assertIs(sim.state, SimState.RUNNING)
        w.radar_screen.disc_btn.click()
        QTest.qWait(500)
        self.assertIs(w.stack.currentWidget(), w.connect_screen)
        w.close()


if __name__ == "__main__":
    unittest.main()
