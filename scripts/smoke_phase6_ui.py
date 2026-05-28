"""Smoke test for Phase 6: settings dialog, sidebar acquisition card,
connect spinner state, first-run picker logic.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Bypass the first-run folder picker for the smoke test (otherwise the modal
# QFileDialog would block forever in this headless context).
os.environ["FNIRS_SKIP_FIRST_RUN"] = "1"

from PySide6.QtWidgets import QApplication

import config
from utils.app_paths import settings_file


def main() -> int:
    app = QApplication([])
    from views.dialogs.settings_dialog import SettingsDialog
    from views.main_window import MainWindow

    # 1. Settings dialog instantiates and loads current values.
    dlg = SettingsDialog(is_recording=False)
    assert dlg.dpf_spin.value() == float(config.DPF), (dlg.dpf_spin.value(), config.DPF)
    assert dlg.distance_spin.value() == float(config.INTEROPTODE_DISTANCE)
    assert dlg.k_sd_spin.value() == float(config.LOAD_DETECTOR_K_SD)
    print(f"SettingsDialog: DPF={dlg.dpf_spin.value()}, dist={dlg.distance_spin.value()}, k_sd={dlg.k_sd_spin.value()}")

    # 2. Acquisition fields disabled when recording.
    dlg_recording = SettingsDialog(is_recording=True)
    assert not dlg_recording.dpf_spin.isEnabled()
    assert not dlg_recording.distance_spin.isEnabled()
    print("SettingsDialog: DPF/distance correctly disabled while recording.")

    # 3. Full MainWindow instantiates.
    win = MainWindow()
    sidebar = win.control_sidebar
    assert sidebar._dpf_value_label.text().startswith("DPF:")
    assert sidebar._distance_value_label.text().startswith("Distance:")
    print(f"ControlSidebar acquisition card: {sidebar._dpf_value_label.text()} / {sidebar._distance_value_label.text()}")

    bar = win.connection_bar
    assert hasattr(bar, "settings_button")
    print(f"ConnectionBar settings button: {bar.settings_button.text()}")

    # 4. Controller exposes Phase 6 reload.
    ctrl = win.controller
    assert callable(ctrl.reload_settings)
    ctrl.reload_settings()  # no-op when no settings.json overrides
    print("Controller.reload_settings: callable and no-op when settings.json empty.")

    # 5. First-run picker only triggers when settings.json absent. Make sure
    #    we don't crash either way.
    sf = settings_file()
    print(f"settings.json exists? {sf.exists()} -> first-run picker {'skipped' if sf.exists() else 'would prompt'}")

    ctrl.close()
    print("\nPHASE 6 smoke test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
