import numpy as np
import pytest

from logic.signal_quality import SignalQualityEvaluator


SAMPLE_RATE = 50.0
WINDOW_S = 5.0


def _make_evaluator(**overrides):
    kwargs = dict(
        num_channels=4,
        sample_rate=SAMPLE_RATE,
        window_s=WINDOW_S,
        hr_recompute_s=1.0,
        std_threshold=0.005,
        cv_threshold=0.05,
        hr_snr_threshold=3.0,
    )
    kwargs.update(overrides)
    return SignalQualityEvaluator(**kwargs)


def _drive(evaluator, signal_per_channel):
    # signal_per_channel: (n_samples, num_channels). Returns last state list.
    last = None
    for i in range(signal_per_channel.shape[0]):
        last = evaluator.update(signal_per_channel[i])
    return last


def _heartbeat_signal(n_samples, fs, hr_hz, amp, mean=1.0, noise_std=0.001):
    t = np.arange(n_samples) / fs
    rng = np.random.default_rng(42)
    return mean + amp * np.sin(2 * np.pi * hr_hz * t) + rng.normal(0, noise_std, n_samples)


def _drift_only_signal(n_samples, fs, slope_per_s=0.5, mean=1.0):
    t = np.arange(n_samples) / fs
    return mean + slope_per_s * t


class TestStartup:
    def test_red_until_window_fills(self):
        ev = _make_evaluator()
        n_per_channel = int(WINDOW_S * SAMPLE_RATE) - 1
        signal = np.ones((n_per_channel, 4)) * 1.0
        out = _drive(ev, signal)
        assert out == ["red"] * 4

    def test_set_sample_rate_resets_buffer(self):
        ev = _make_evaluator()
        _drive(ev, np.ones((int(WINDOW_S * SAMPLE_RATE), 4)) * 1.0)
        ev.set_sample_rate(100.0)
        # Buffer was reallocated so we should be red again on the next sample.
        out = ev.update(np.ones(4))
        assert out == ["red"] * 4


class TestZeroAndFlatlined:
    def test_all_zero_signal_is_red(self):
        ev = _make_evaluator()
        n = int(WINDOW_S * SAMPLE_RATE) + int(2 * SAMPLE_RATE)
        out = _drive(ev, np.zeros((n, 4)))
        assert out == ["red"] * 4

    def test_constant_nonzero_is_red(self):
        # No variance -> std fails. No heartbeat -> HR fails. CV passes
        # (std=0 < threshold), so 1/3 -> red.
        ev = _make_evaluator()
        n = int(WINDOW_S * SAMPLE_RATE) + int(2 * SAMPLE_RATE)
        out = _drive(ev, np.ones((n, 4)) * 1.0)
        assert out == ["red"] * 4


class TestHeartbeatDetection:
    def test_clean_heartbeat_signal_is_green(self):
        # 1.2 Hz sine + small noise. Amplitude large enough to ensure SNR
        # in the HR band well above 3x the 2.5-5 Hz median.
        n = int(8 * SAMPLE_RATE)
        sig = _heartbeat_signal(n, SAMPLE_RATE, hr_hz=1.2, amp=0.05, mean=1.0, noise_std=0.001)
        signal = np.column_stack([sig, sig, sig, sig])
        ev = _make_evaluator()
        out = _drive(ev, signal)
        assert all(s == "green" for s in out), out

    def test_no_heartbeat_only_drift_is_red_or_yellow(self):
        # Pure linear drift: std passes, but CV fails (slope dominates), and
        # no heartbeat in the band -> at most 1/3 -> red.
        n = int(8 * SAMPLE_RATE)
        sig = _drift_only_signal(n, SAMPLE_RATE, slope_per_s=2.0, mean=1.0)
        signal = np.column_stack([sig, sig, sig, sig])
        ev = _make_evaluator()
        out = _drive(ev, signal)
        # std passes (linear drift has variance), CV may pass or fail
        # depending on magnitudes; HR fails. So expect red or yellow.
        for s in out:
            assert s in ("red", "yellow"), out


class TestMixedChannels:
    def test_independent_per_channel_evaluation(self):
        # Channel 0: clean heartbeat -> green.
        # Channel 1: zeros -> red.
        # Channel 2: drift only -> not green.
        # Channel 3: heartbeat -> green.
        n = int(8 * SAMPLE_RATE)
        ch0 = _heartbeat_signal(n, SAMPLE_RATE, hr_hz=1.2, amp=0.05, mean=1.0, noise_std=0.001)
        ch1 = np.zeros(n)
        ch2 = _drift_only_signal(n, SAMPLE_RATE, slope_per_s=2.0, mean=1.0)
        ch3 = _heartbeat_signal(n, SAMPLE_RATE, hr_hz=1.4, amp=0.05, mean=1.0, noise_std=0.001)
        signal = np.column_stack([ch0, ch1, ch2, ch3])
        ev = _make_evaluator()
        out = _drive(ev, signal)
        assert out[0] == "green", out
        assert out[1] == "red", out
        assert out[2] in ("red", "yellow"), out
        assert out[3] == "green", out


class TestReset:
    def test_reset_returns_to_red(self):
        ev = _make_evaluator()
        n = int(8 * SAMPLE_RATE)
        sig = _heartbeat_signal(n, SAMPLE_RATE, hr_hz=1.2, amp=0.05, mean=1.0, noise_std=0.001)
        _drive(ev, np.column_stack([sig] * 4))
        ev.reset()
        out = ev.update(np.ones(4))
        assert out == ["red"] * 4


class TestInputValidation:
    def test_wrong_shape_raises(self):
        ev = _make_evaluator()
        with pytest.raises(ValueError):
            ev.update(np.ones(3))  # need 4 channels
