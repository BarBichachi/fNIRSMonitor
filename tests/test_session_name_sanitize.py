import os
import shutil
import tempfile

from utils.session_naming import sanitize_session_name
from utils.session_recorder import SessionRecorder


class TestSanitizeSessionName:
    def test_strips_windows_illegal_chars(self):
        assert sanitize_session_name("Trial:1") == "Trial1"
        assert sanitize_session_name("a/b\\c") == "abc"
        assert sanitize_session_name('na<me>?*"|') == "name"

    def test_trims_trailing_dot_and_space(self):
        assert sanitize_session_name("name. ") == "name"
        assert sanitize_session_name("  spaced  ") == "spaced"

    def test_fallback_when_nothing_usable(self):
        assert sanitize_session_name("") == "session"
        assert sanitize_session_name(":::") == "session"
        assert sanitize_session_name(None) == "session"

    def test_custom_fallback(self):
        assert sanitize_session_name("***", fallback="rec") == "rec"

    def test_keeps_normal_names(self):
        assert sanitize_session_name("SleepExperiment_01") == "SleepExperiment_01"
        assert sanitize_session_name("subj 3 nback") == "subj 3 nback"


def test_illegal_name_does_not_crash_start():
    # An operator typing a Windows-reserved character must never crash the
    # recorder's folder creation.
    root = tempfile.mkdtemp(prefix="fnirs_name_")
    try:
        rec = SessionRecorder(recordings_root=root)
        rec.start(
            "Trial:1?*",
            stream_info={"name": "t", "type": "NIRS", "source_id": "X"},
            sample_rate=50.0,
            config_snapshot={"DPF": 6.56, "INTEROPTODE_DISTANCE": 3.5},
        )
        assert rec.is_recording
        assert rec.session_folder is not None
        assert os.path.isdir(rec.session_folder)

        base = os.path.basename(rec.session_folder)
        for ch in '<>:"/\\|?*':
            assert ch not in base

        rec.stop()
    finally:
        shutil.rmtree(root, ignore_errors=True)
