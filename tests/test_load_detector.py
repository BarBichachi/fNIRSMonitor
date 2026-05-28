import numpy as np
import pytest

from logic.load_detector import ThresholdAsymmetryDetector, LEFT_INDICES, RIGHT_INDICES
from utils.enums import CognitiveState


# Use compact windows so tests run in a reasonable time. The behavior under
# test is window-fill driven, not absolute-time driven.
SAMPLE_RATE = 50.0
REST_S = 2.0          # 100 samples calibration window
ACTIVE_S = 1.0        # 50 samples active window


def _make_detector(**overrides):
    kwargs = dict(
        sample_rate=SAMPLE_RATE,
        rest_window_s=REST_S,
        active_window_s=ACTIVE_S,
        k_sd=1.5,
        min_elevated_channels=2,
        hhb_tol_um=0.5,
    )
    kwargs.update(overrides)
    return ThresholdAsymmetryDetector(**kwargs)


def _quiet_o2hb(rng) -> np.ndarray:
    # Symmetric, small-amplitude rest signal. Tight per-channel SD.
    return rng.normal(0.0, 0.05, size=8)


def _quiet_hhb(rng) -> np.ndarray:
    return rng.normal(0.0, 0.02, size=8)


def _green_quality() -> list:
    return ["green"] * 8


def _calibrate_quiet(det: ThresholdAsymmetryDetector, n_samples: int = None) -> None:
    rng = np.random.default_rng(42)
    n = n_samples if n_samples is not None else int(REST_S * SAMPLE_RATE)
    det.start_calibration()
    for _ in range(n):
        det.update(_quiet_o2hb(rng), _quiet_hhb(rng), _green_quality())


class TestPreCalibration:
    def test_returns_nominal_when_not_calibrated(self):
        det = _make_detector()
        out = det.update(np.zeros(8), np.zeros(8), _green_quality())
        assert out == CognitiveState.NOMINAL
        assert not det.is_calibrated
        assert not det.is_calibrating

    def test_baseline_summary_is_none_before_calibration(self):
        det = _make_detector()
        assert det.baseline_summary is None


class TestCalibration:
    def test_state_is_calibrating_during_collection(self):
        det = _make_detector()
        det.start_calibration()
        out = det.update(np.zeros(8), np.zeros(8), _green_quality())
        assert out == CognitiveState.CALIBRATING
        assert det.is_calibrating

    def test_progress_increases_monotonically(self):
        det = _make_detector()
        det.start_calibration()
        prog = []
        rng = np.random.default_rng(0)
        for _ in range(int(REST_S * SAMPLE_RATE)):
            det.update(_quiet_o2hb(rng), _quiet_hhb(rng), _green_quality())
            prog.append(det.calibration_progress)
        # Monotonic non-decreasing, ends at 1.0.
        assert all(prog[i] <= prog[i + 1] + 1e-9 for i in range(len(prog) - 1))
        assert prog[-1] >= 0.99

    def test_calibration_finalizes_after_window(self):
        det = _make_detector()
        _calibrate_quiet(det)
        assert det.is_calibrated
        assert not det.is_calibrating
        summary = det.baseline_summary
        assert summary is not None
        assert len(summary["mean_o2hb"]) == 8
        assert len(summary["std_o2hb"]) == 8


class TestPostCalibration:
    def test_quiet_input_after_calibration_stays_nominal(self):
        det = _make_detector()
        _calibrate_quiet(det)
        rng = np.random.default_rng(7)
        # Drive a full active window of quiet, then a few more samples.
        for _ in range(int((ACTIVE_S + 0.5) * SAMPLE_RATE)):
            out = det.update(_quiet_o2hb(rng), _quiet_hhb(rng), _green_quality())
        assert out == CognitiveState.NOMINAL

    def test_right_pfc_elevation_triggers_load(self):
        det = _make_detector()
        _calibrate_quiet(det)

        # Sustained right-PFC O2Hb elevation with HHb flat. Baseline SD is
        # small (~0.05), so k_sd=1.5 means threshold ~0.075. We push the
        # right channels well above that.
        rng = np.random.default_rng(11)
        out = CognitiveState.NOMINAL
        for _ in range(int(2.0 * SAMPLE_RATE)):
            o2 = _quiet_o2hb(rng)
            for ch in RIGHT_INDICES:
                o2[ch] = 0.5  # well above baseline + k_sd*SD
            hh = _quiet_hhb(rng)  # HHb stays near zero, sanity gate OK
            out = det.update(o2, hh, _green_quality())
        assert out == CognitiveState.LOAD

    def test_hhb_gate_blocks_motion_artifact(self):
        det = _make_detector()
        _calibrate_quiet(det)

        rng = np.random.default_rng(13)
        out = CognitiveState.NOMINAL
        for _ in range(int(2.0 * SAMPLE_RATE)):
            o2 = _quiet_o2hb(rng)
            hh = _quiet_hhb(rng)
            for ch in RIGHT_INDICES:
                o2[ch] = 0.5
                hh[ch] = 1.0  # HHb also up -> looks like motion/systemic
            out = det.update(o2, hh, _green_quality())
        # Per-channel path is gated by HHb, AND the asymmetry path requires
        # right > left in O2Hb only. Right O2Hb IS up here, so asymmetry path
        # might still fire. Verify the per-channel HHb gate at least: feed
        # bilateral motion (both sides up) so asymmetry doesn't fire either.
        for _ in range(int(2.0 * SAMPLE_RATE)):
            o2 = _quiet_o2hb(rng) + 0.5  # everyone up
            hh = _quiet_hhb(rng) + 1.0   # everyone up (motion)
            out = det.update(o2, hh, _green_quality())
        assert out == CognitiveState.NOMINAL, (
            "Bilateral O2Hb+HHb elevation must not trigger LOAD (motion artifact)."
        )

    def test_bad_quality_channel_does_not_count(self):
        det = _make_detector()
        _calibrate_quiet(det)
        rng = np.random.default_rng(17)
        # 3 right channels elevated, but 2 of them flagged red. Only 1 good
        # elevated channel -> below min_elevated_channels=2. Asymmetry path
        # may still fire because asymmetry doesn't gate on quality. So we
        # check the channel gate specifically by feeding LEFT also up (cancels
        # asymmetry) plus right-only quality being red.
        for _ in range(int(2.0 * SAMPLE_RATE)):
            o2 = _quiet_o2hb(rng)
            for ch in RIGHT_INDICES:
                o2[ch] = 0.5
            # Match left so asymmetry path stays nominal.
            for ch in LEFT_INDICES:
                o2[ch] = 0.5
            hh = _quiet_hhb(rng)
            quality = ["green"] * 8
            quality[RIGHT_INDICES[0]] = "red"
            quality[RIGHT_INDICES[1]] = "red"
            quality[RIGHT_INDICES[2]] = "red"
            out = det.update(o2, hh, quality)
        assert out == CognitiveState.NOMINAL


class TestReset:
    def test_reset_clears_baseline(self):
        det = _make_detector()
        _calibrate_quiet(det)
        assert det.is_calibrated
        det.reset()
        assert not det.is_calibrated
        assert det.baseline_summary is None

    def test_recalibration_after_reset(self):
        det = _make_detector()
        _calibrate_quiet(det)
        det.reset()
        _calibrate_quiet(det)
        assert det.is_calibrated


class TestSampleRateChange:
    def test_active_window_resizes(self):
        det = _make_detector()
        det.set_sample_rate(100.0)
        # active_window_s=1.0 at fs=100 -> 100 samples maxlen
        assert det._active_o2.maxlen == 100
        assert det._active_hhb.maxlen == 100
