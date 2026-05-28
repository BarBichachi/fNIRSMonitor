from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import config
from config.schema import SettingsValidationError
from config.user_settings import load as load_user_settings, save as save_user_settings
from utils.app_paths import default_recordings_dir


class SettingsDialog(QDialog):
    # Tabbed settings dialog. Loads current values from the merged config,
    # writes user overrides to settings.json on OK, and triggers a controller
    # reload so the running app picks them up.
    #
    # Acquisition fields (DPF, interoptode distance) are disabled when a
    # recording is in progress, because changing those mid-recording would
    # silently invalidate the data.

    def __init__(self, is_recording: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setObjectName("SettingsDialog")
        self.setMinimumWidth(480)
        self._is_recording = is_recording

        self._build_ui()
        self._load_current_values()

    # ---------- UI construction ----------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_general_tab(), "General")
        self.tabs.addTab(self._build_acquisition_tab(), "Acquisition")
        self.tabs.addTab(self._build_calibration_tab(), "Calibration")
        self.tabs.addTab(self._build_alerting_tab(), "Alerting")
        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        # Recordings folder with Browse.
        folder_row = QWidget()
        folder_layout = QHBoxLayout(folder_row)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        self.recordings_root_edit = QLineEdit()
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_recordings_folder)
        folder_layout.addWidget(self.recordings_root_edit)
        folder_layout.addWidget(browse_btn)
        form.addRow("Recordings folder:", folder_row)

        self.reconnect_tolerance_spin = QDoubleSpinBox()
        self.reconnect_tolerance_spin.setRange(0.5, 60.0)
        self.reconnect_tolerance_spin.setSingleStep(0.5)
        self.reconnect_tolerance_spin.setSuffix(" s")
        form.addRow("Reconnect tolerance:", self.reconnect_tolerance_spin)

        self.sound_suppress_spin = QDoubleSpinBox()
        self.sound_suppress_spin.setRange(0.0, 60.0)
        self.sound_suppress_spin.setSingleStep(0.5)
        self.sound_suppress_spin.setSuffix(" s")
        form.addRow("Nominal-sound suppress:", self.sound_suppress_spin)

        return widget

    def _build_acquisition_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        if self._is_recording:
            warn = QLabel(
                "Acquisition parameters are locked while a recording is in "
                "progress. Stop recording to edit DPF or interoptode distance."
            )
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #fbc02d;")
            form.addRow(warn)

        self.dpf_spin = QDoubleSpinBox()
        self.dpf_spin.setRange(1.0, 12.0)
        self.dpf_spin.setSingleStep(0.01)
        self.dpf_spin.setDecimals(2)
        self.dpf_spin.setEnabled(not self._is_recording)
        form.addRow("DPF:", self.dpf_spin)

        self.distance_spin = QDoubleSpinBox()
        self.distance_spin.setRange(0.5, 10.0)
        self.distance_spin.setSingleStep(0.1)
        self.distance_spin.setDecimals(2)
        self.distance_spin.setSuffix(" cm")
        self.distance_spin.setEnabled(not self._is_recording)
        form.addRow("Interoptode distance:", self.distance_spin)

        wl_label = QLabel(str(config.WAVELENGTH_ORDER))
        form.addRow("Wavelength order (read-only):", wl_label)

        ext_label = QLabel(self._format_extinction_coefficients())
        ext_label.setWordWrap(True)
        ext_label.setStyleSheet("color: #bcc1cc; font-size: 12px;")
        form.addRow("Extinction (Matcher 1995):", ext_label)

        return widget

    def _build_calibration_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self.baseline_mode_combo = QComboBox()
        self.baseline_mode_combo.addItem("single_sample (matches OxySoft)", "single_sample")
        self.baseline_mode_combo.addItem("window (average over N seconds)", "window")
        form.addRow("Baseline mode:", self.baseline_mode_combo)

        self.baseline_window_spin = QDoubleSpinBox()
        self.baseline_window_spin.setRange(1.0, 120.0)
        self.baseline_window_spin.setSingleStep(1.0)
        self.baseline_window_spin.setSuffix(" s")
        form.addRow("Baseline window:", self.baseline_window_spin)

        self.detector_rest_spin = QDoubleSpinBox()
        self.detector_rest_spin.setRange(10.0, 600.0)
        self.detector_rest_spin.setSingleStep(5.0)
        self.detector_rest_spin.setSuffix(" s")
        form.addRow("Per-subject calibration:", self.detector_rest_spin)

        return widget

    def _build_alerting_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self.k_sd_spin = QDoubleSpinBox()
        self.k_sd_spin.setRange(0.1, 10.0)
        self.k_sd_spin.setSingleStep(0.1)
        form.addRow("k_sd (elevation threshold):", self.k_sd_spin)

        self.active_window_spin = QDoubleSpinBox()
        self.active_window_spin.setRange(1.0, 300.0)
        self.active_window_spin.setSingleStep(1.0)
        self.active_window_spin.setSuffix(" s")
        form.addRow("Active window:", self.active_window_spin)

        self.min_elevated_spin = QSpinBox()
        self.min_elevated_spin.setRange(1, 4)
        form.addRow("Min elevated channels (right):", self.min_elevated_spin)

        self.hhb_tol_spin = QDoubleSpinBox()
        self.hhb_tol_spin.setRange(0.0, 10.0)
        self.hhb_tol_spin.setSingleStep(0.05)
        self.hhb_tol_spin.setSuffix(" uM")
        form.addRow("HHb sanity tolerance:", self.hhb_tol_spin)

        return widget

    # ---------- Load / save ----------

    def _load_current_values(self):
        # Recordings root is special: None = "use platform default", show
        # the default path as a hint but let the user override.
        current_root = config.RECORDINGS_ROOT or str(default_recordings_dir())
        self.recordings_root_edit.setText(current_root)
        self.reconnect_tolerance_spin.setValue(float(config.RECONNECT_TOLERANCE_S))
        self.sound_suppress_spin.setValue(float(config.SOUND_NOMINAL_SUPPRESS_S))

        self.dpf_spin.setValue(float(config.DPF))
        self.distance_spin.setValue(float(config.INTEROPTODE_DISTANCE))

        # Baseline mode combo: select by data value.
        idx = self.baseline_mode_combo.findData(str(config.BASELINE_MODE))
        if idx >= 0:
            self.baseline_mode_combo.setCurrentIndex(idx)
        self.baseline_window_spin.setValue(float(config.BASELINE_WINDOW_S))
        self.detector_rest_spin.setValue(float(config.LOAD_DETECTOR_REST_WINDOW_S))

        self.k_sd_spin.setValue(float(config.LOAD_DETECTOR_K_SD))
        self.active_window_spin.setValue(float(config.LOAD_DETECTOR_ACTIVE_WINDOW_S))
        self.min_elevated_spin.setValue(int(config.LOAD_DETECTOR_MIN_ELEVATED_CHANNELS))
        self.hhb_tol_spin.setValue(float(config.LOAD_DETECTOR_HHB_TOL_UM))

    def _collect_overrides(self) -> dict:
        # Build the dict that gets passed to user_settings.save. Only includes
        # values that differ from the current effective config; that way
        # settings.json stays minimal and tracks user intent.
        overrides = {}
        root_text = self.recordings_root_edit.text().strip()
        default_root = str(default_recordings_dir())
        # If user left it as the default, store None (so future default
        # changes propagate). Otherwise store the explicit path.
        overrides["RECORDINGS_ROOT"] = None if root_text == default_root else root_text

        overrides["RECONNECT_TOLERANCE_S"] = self.reconnect_tolerance_spin.value()
        overrides["SOUND_NOMINAL_SUPPRESS_S"] = self.sound_suppress_spin.value()

        if not self._is_recording:
            overrides["DPF"] = self.dpf_spin.value()
            overrides["INTEROPTODE_DISTANCE"] = self.distance_spin.value()

        overrides["BASELINE_MODE"] = self.baseline_mode_combo.currentData()
        overrides["BASELINE_WINDOW_S"] = self.baseline_window_spin.value()
        overrides["LOAD_DETECTOR_REST_WINDOW_S"] = self.detector_rest_spin.value()

        overrides["LOAD_DETECTOR_K_SD"] = self.k_sd_spin.value()
        overrides["LOAD_DETECTOR_ACTIVE_WINDOW_S"] = self.active_window_spin.value()
        overrides["LOAD_DETECTOR_MIN_ELEVATED_CHANNELS"] = self.min_elevated_spin.value()
        overrides["LOAD_DETECTOR_HHB_TOL_UM"] = self.hhb_tol_spin.value()

        return overrides

    def _on_ok(self):
        # Merge our overrides on top of whatever the user already has in
        # settings.json. This preserves keys we don't expose in the UI.
        try:
            existing = load_user_settings()
        except SettingsValidationError as ex:
            # Existing file is invalid. Warn but proceed; our writes will
            # replace the bad values with valid ones.
            QMessageBox.warning(
                self,
                "Settings",
                f"Existing settings.json had problems and will be repaired:\n{ex}",
            )
            existing = {}

        existing.update(self._collect_overrides())

        try:
            save_user_settings(existing)
        except SettingsValidationError as ex:
            QMessageBox.critical(self, "Settings", f"Invalid setting:\n{ex}")
            return
        except Exception as ex:
            QMessageBox.critical(self, "Settings", f"Failed to save settings:\n{ex}")
            return

        self.accept()

    def _browse_recordings_folder(self):
        start_dir = self.recordings_root_edit.text().strip() or str(default_recordings_dir())
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose recordings folder", start_dir
        )
        if chosen:
            self.recordings_root_edit.setText(chosen)

    @staticmethod
    def _format_extinction_coefficients() -> str:
        ext = config.EXTINCTION_COEFFICIENTS
        lines = []
        for wl in ("760nm", "850nm"):
            if wl in ext:
                pair = ext[wl]
                lines.append(
                    f"{wl}: O2Hb={pair.get('O2Hb')}, HHb={pair.get('HHb')}"
                )
        return "\n".join(lines)
