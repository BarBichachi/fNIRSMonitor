import numpy as np
import pytest

import config
from logic.data_processor import DataProcessor
from utils.enums import CognitiveState


# An "active" OD sample looks like the real OxySoft output: indices 0..7 and
# 24..31 (the 16 active channel positions for OctaMon) carry signal-like
# values, the rest sit at the saturation placeholder.
def _build_od_sample(level: float = 1.0) -> list:
    od = [config.PLACEHOLDER_HI] * 32
    active_indices = list(range(0, 8)) + list(range(24, 32))
    for i in active_indices:
        od[i] = level
    return od


def _placeholder_sample() -> list:
    return [config.PLACEHOLDER_HI] * 32


@pytest.fixture(autouse=True)
def reset_baseline_mode():
    # Each test starts in single_sample mode; restore at teardown.
    original = getattr(config, "BASELINE_MODE", "single_sample")
    config.BASELINE_MODE = "single_sample"
    yield
    config.BASELINE_MODE = original


class TestSingleSampleMode:
    def test_first_valid_sample_becomes_baseline(self):
        dp = DataProcessor()
        dp.set_sample_rate(50.0)
        dp.set_baseline_mode("single_sample")

        rules = {"threshold": 1e9, "duration": 1}

        # Placeholder is dropped.
        assert dp.process_sample_od(_placeholder_sample(), rules) is None

        # First valid sample establishes baseline; raw deltas are 0.
        first = dp.process_sample_od(_build_od_sample(1.0), rules)
        assert first is not None
        assert np.allclose(first["O2Hb_raw"], 0.0)
        assert np.allclose(first["HHb_raw"], 0.0)
        assert first["alert_state"] != CognitiveState.WARMING_UP

    def test_subsequent_samples_produce_real_deltas(self):
        dp = DataProcessor()
        dp.set_sample_rate(50.0)
        dp.set_baseline_mode("single_sample")
        rules = {"threshold": 1e9, "duration": 1}

        dp.process_sample_od(_build_od_sample(1.0), rules)
        second = dp.process_sample_od(_build_od_sample(1.05), rules)
        # delta_OD = 0.05 on all active channels; resulting raw Hb should be non-zero.
        assert second is not None
        assert any(abs(v) > 1e-6 for v in second["O2Hb_raw"]), second["O2Hb_raw"]


class TestWindowMode:
    def test_warming_up_until_window_fills(self):
        dp = DataProcessor()
        dp.set_sample_rate(50.0)
        # Switch into window mode AFTER setting rate so window_samples is correct.
        dp.set_baseline_mode("window")
        # Override window length to a manageable size for the test.
        dp.baseline_window_samples = 20
        rules = {"threshold": 1e9, "duration": 1}

        for i in range(19):
            r = dp.process_sample_od(_build_od_sample(1.0 + i * 1e-4), rules)
            assert r is not None
            assert r["alert_state"] == CognitiveState.WARMING_UP
            assert r["O2Hb_raw"] is None
            assert r["HHb_raw"] is None

        # 20th sample completes the buffer and produces a real (delta) row.
        twentieth = dp.process_sample_od(_build_od_sample(1.05), rules)
        assert twentieth is not None
        assert twentieth["alert_state"] != CognitiveState.WARMING_UP
        assert twentieth["O2Hb_raw"] is not None


class TestManualRecompute:
    def test_recompute_with_empty_history_returns_false(self):
        dp = DataProcessor()
        dp.set_sample_rate(50.0)
        assert dp.recompute_baseline_from_window() is False

    def test_recompute_changes_baseline(self):
        dp = DataProcessor()
        dp.set_sample_rate(50.0)
        dp.set_baseline_mode("single_sample")
        rules = {"threshold": 1e9, "duration": 1}

        # Feed a few samples; first one sets baseline.
        dp.process_sample_od(_build_od_sample(1.0), rules)
        dp.process_sample_od(_build_od_sample(1.05), rules)
        dp.process_sample_od(_build_od_sample(1.10), rules)

        baseline_before = dp.baseline_od.copy()
        ok = dp.recompute_baseline_from_window()
        assert ok
        baseline_after = dp.baseline_od

        # New baseline should be the mean of the buffered OD history, which
        # differs from the first sample (used as baseline before).
        assert not np.allclose(baseline_before, baseline_after)


class TestModeSwitch:
    def test_switching_mode_resets_baseline(self):
        dp = DataProcessor()
        dp.set_sample_rate(50.0)
        rules = {"threshold": 1e9, "duration": 1}
        dp.process_sample_od(_build_od_sample(1.0), rules)
        assert dp.baseline_od is not None

        dp.set_baseline_mode("window")
        assert dp.baseline_od is None
