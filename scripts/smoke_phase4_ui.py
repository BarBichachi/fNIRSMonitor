"""Smoke test: instantiate the full main window once, verify Phase 4 wiring."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication


def main() -> int:
    app = QApplication([])
    from views.main_window import MainWindow

    win = MainWindow()
    sidebar = win.alert_sidebar

    # Calibration UI exists.
    assert hasattr(sidebar, "calibrate_button"), "Calibrate button missing"
    assert sidebar.calibrate_button.text() == "Calibrate Subject (60s)"
    assert sidebar.calibration_status_label.text() == "Not calibrated yet."
    print("UI: calibration controls present.")

    # Controller exposes Phase 4 methods.
    ctrl = win.controller
    assert callable(ctrl.start_load_calibration)
    assert callable(ctrl.get_load_detector_status)
    status = ctrl.get_load_detector_status()
    assert status == {
        "is_calibrating": False,
        "is_calibrated": False,
        "progress": 0.0,
        "baseline_summary": None,
    }, status
    print("Controller: load detector status (no connection):", status)

    # start_load_calibration without a connection returns False.
    assert ctrl.start_load_calibration() is False
    print("Controller: start_load_calibration refused when not connected.")

    # Poll timer is running.
    assert win.calibration_poll_timer.isActive()
    print("UI: calibration poll timer active.")

    ctrl.close()
    print("\nPHASE 4 smoke test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
