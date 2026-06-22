import shutil
import tempfile

import pytest

from PySide6.QtWidgets import QApplication

from logic.app_controller import AppController


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _connected_controller(tmp_root: str) -> AppController:
    # Build a controller and put it in a "connected" state without a real LSL
    # stream, so the recording state machine can be exercised directly.
    ctrl = AppController()
    ctrl.recorder.recordings_root = tmp_root
    ctrl.is_connected = True
    ctrl.connected_source_id = "SRC-1"
    ctrl.connected_stream_name = "sim"
    ctrl.detected_stream_rate = 50.0
    return ctrl


def _write_some_rows(ctrl, n=10):
    for i in range(n):
        ctrl.recorder.write(
            [1.0] * 32, [0.1] * 8, [0.05] * 8,
            adc=1, event=0, dropped=False, timestamp=i / 50.0,
        )


def test_start_then_stop_emits_lifecycle(qapp):
    root = tempfile.mkdtemp(prefix="fnirs_sm_")
    ctrl = _connected_controller(root)
    events = []
    ctrl.recording_state_changed.connect(events.append)
    try:
        ctrl.start_recording("Test_01")
        assert ctrl.recorder.is_recording
        assert events == ["started"]

        ctrl.stop_recording()
        assert not ctrl.recorder.is_recording
        assert events == ["started", "stopped"]
    finally:
        ctrl.close()
        shutil.rmtree(root, ignore_errors=True)


def test_transient_drop_pauses_not_stops_then_resumes(qapp):
    # The core of the decoupling fix: a non-user stream drop must PAUSE the
    # recording (files stay open) and a returning stream must RESUME the same
    # recording, never tearing it down.
    root = tempfile.mkdtemp(prefix="fnirs_sm_")
    ctrl = _connected_controller(root)
    events = []
    ctrl.recording_state_changed.connect(events.append)
    try:
        ctrl.start_recording("Test_01")
        _write_some_rows(ctrl, 10)

        # Simulate a watchdog / network drop (not user-initiated).
        ctrl._user_initiated_disconnect = False
        ctrl._on_disconnected()

        assert ctrl.recorder.is_recording, "recording must stay open across a blip"
        assert ctrl.recorder.is_paused
        assert events[-1] == "paused"

        # The same stream returns.
        ctrl._on_connected("sim")

        assert ctrl.recorder.is_recording
        assert not ctrl.recorder.is_paused
        assert events[-1] == "resumed"

        ctrl.stop_recording()
        assert events == ["started", "paused", "resumed", "stopped"]
    finally:
        ctrl.close()
        shutil.rmtree(root, ignore_errors=True)


def test_user_disconnect_stops_recording(qapp):
    root = tempfile.mkdtemp(prefix="fnirs_sm_")
    ctrl = _connected_controller(root)
    events = []
    ctrl.recording_state_changed.connect(events.append)
    try:
        ctrl.start_recording("Test_01")
        _write_some_rows(ctrl, 5)

        # User clicked Disconnect: this path stops the recording outright.
        ctrl._user_initiated_disconnect = True
        ctrl._on_disconnected()

        assert not ctrl.recorder.is_recording
        assert events == ["started", "stopped"]
    finally:
        ctrl.close()
        shutil.rmtree(root, ignore_errors=True)
