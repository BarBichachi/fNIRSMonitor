import datetime
import os
import shutil
import tempfile

import pytest

from utils.session_naming import (
    split_name_and_index,
    format_name,
    get_next_index_for_prefix,
    get_today_recordings_folder,
)


class TestSplitNameAndIndex:
    def test_name_only(self):
        assert split_name_and_index("SleepExperiment") == ("SleepExperiment", None)

    def test_name_with_index(self):
        assert split_name_and_index("SleepExperiment_01") == ("SleepExperiment", 1)
        assert split_name_and_index("Trial_42") == ("Trial", 42)

    def test_empty_string(self):
        assert split_name_and_index("") == ("", None)

    def test_whitespace_trimmed(self):
        assert split_name_and_index("  Foo_03  ") == ("Foo", 3)

    def test_none_input(self):
        assert split_name_and_index(None) == ("", None)

    def test_index_with_leading_zeros(self):
        assert split_name_and_index("X_007") == ("X", 7)


class TestFormatName:
    def test_two_digit_padding(self):
        assert format_name("Foo", 1) == "Foo_01"
        assert format_name("Foo", 12) == "Foo_12"

    def test_three_digit_value(self):
        # Format only pads to 2 digits; larger numbers stay unpadded.
        assert format_name("Foo", 123) == "Foo_123"


class TestGetNextIndexForPrefix:
    def _make_root(self):
        return tempfile.mkdtemp(prefix="fnirs_naming_test_")

    def test_empty_folder_returns_one(self):
        root = self._make_root()
        try:
            assert get_next_index_for_prefix(root, "Trial") == 1
        finally:
            shutil.rmtree(root)

    def test_recognizes_new_per_recording_folders(self):
        root = self._make_root()
        try:
            date = datetime.datetime.now().strftime("%d-%m-%Y")
            folder = os.path.join(root, date)
            os.makedirs(folder)
            # Per-recording folders are named HH-MM-SS_<prefix>_NN.
            os.makedirs(os.path.join(folder, "10-00-00_Trial_01"))
            os.makedirs(os.path.join(folder, "11-00-00_Trial_02"))
            os.makedirs(os.path.join(folder, "12-00-00_OtherSession_01"))

            assert get_next_index_for_prefix(root, "Trial") == 3
            assert get_next_index_for_prefix(root, "OtherSession") == 2
            assert get_next_index_for_prefix(root, "NotPresent") == 1
        finally:
            shutil.rmtree(root)

    def test_recognizes_legacy_flat_files(self):
        # Pre-Phase-1 layout placed files directly in the date folder named
        # <date>_<time>_<prefix>_NN_RawOD.txt. The scanner still reads those.
        root = self._make_root()
        try:
            date = datetime.datetime.now().strftime("%d-%m-%Y")
            folder = os.path.join(root, date)
            os.makedirs(folder)
            open(os.path.join(folder, f"{date}_10-00-00_Legacy_05_RawOD.txt"), "w").close()
            open(os.path.join(folder, f"{date}_11-00-00_Legacy_07_RawOD.txt"), "w").close()

            assert get_next_index_for_prefix(root, "Legacy") == 8
        finally:
            shutil.rmtree(root)

    def test_mixed_new_and_legacy(self):
        root = self._make_root()
        try:
            date = datetime.datetime.now().strftime("%d-%m-%Y")
            folder = os.path.join(root, date)
            os.makedirs(folder)
            os.makedirs(os.path.join(folder, "10-00-00_Mixed_03"))
            open(os.path.join(folder, f"{date}_11-00-00_Mixed_09_RawOD.txt"), "w").close()
            assert get_next_index_for_prefix(root, "Mixed") == 10
        finally:
            shutil.rmtree(root)

    def test_case_insensitive(self):
        root = self._make_root()
        try:
            date = datetime.datetime.now().strftime("%d-%m-%Y")
            folder = os.path.join(root, date)
            os.makedirs(folder)
            os.makedirs(os.path.join(folder, "10-00-00_Case_04"))
            assert get_next_index_for_prefix(root, "case") == 5
            assert get_next_index_for_prefix(root, "CASE") == 5
        finally:
            shutil.rmtree(root)


class TestGetTodayRecordingsFolder:
    def test_creates_folder_if_missing(self):
        root = tempfile.mkdtemp(prefix="fnirs_today_test_")
        try:
            shutil.rmtree(root)  # ensure root doesn't exist
            folder = get_today_recordings_folder(root)
            assert os.path.exists(folder)
            assert os.path.isdir(folder)
        finally:
            if os.path.exists(root):
                shutil.rmtree(root)
