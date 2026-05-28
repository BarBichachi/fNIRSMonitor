import os
import shutil
import tempfile

import h5py
import numpy as np

from utils.session_recorder import SessionRecorder


def _cfg_snapshot() -> dict:
    return {
        "DPF": 6.56,
        "INTEROPTODE_DISTANCE": 3.5,
        "WAVELENGTH_ORDER": ("850nm", "760nm"),
        "EXTINCTION_COEFFICIENTS": {
            "760nm": {"O2Hb": 0.586, "HHb": 1.548},
            "850nm": {"O2Hb": 1.058, "HHb": 0.781},
        },
        "CHANNEL_NAMES": ["L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4"],
    }


def test_stop_emits_snirf_with_real_samples_only():
    root = tempfile.mkdtemp(prefix="fnirs_snirf_test_")
    try:
        rec = SessionRecorder(recordings_root=root)
        rec.start(
            "SnirfTest_01",
            stream_info={"name": "Test", "type": "NIRS", "source_id": "TEST-001"},
            sample_rate=50.0,
            config_snapshot=_cfg_snapshot(),
        )

        n_real = 80
        for i in range(n_real):
            t = i / 50.0
            o2 = [0.1 * i + 0.01 * j for j in range(8)]
            hh = [-0.05 * i + 0.005 * j for j in range(8)]
            rec.write([1.0] * 32, o2, hh, adc=42, event=0, dropped=False, timestamp=t)

        # A handful of sentinel rows that should NOT make it into SNIRF.
        for i in range(5):
            rec.write([float("nan")] * 32, None, None, adc=42, event=0,
                      dropped=True, timestamp=(n_real + i) / 50.0)
        # And a couple of "warming up" rows (o2hb/hhb None, dropped=False).
        for i in range(3):
            rec.write([1.0] * 32, None, None, adc=42, event=0, dropped=False,
                      timestamp=(n_real + 5 + i) / 50.0)

        rec.stop()

        # SNIRF must exist alongside the TSVs.
        snirf_path = os.path.join(rec.session_folder, "session.snirf")
        assert os.path.exists(snirf_path), snirf_path

        with h5py.File(snirf_path, "r") as f:
            assert f["formatVersion"][()].decode("utf-8") == "1.1"
            ds = f["nirs/data1/dataTimeSeries"]
            # Only the n_real real samples should be present; sentinels stripped.
            assert ds.shape == (n_real, 16), ds.shape

            # Spot check: column 0 (Ch0 HbO) should track 0.1 * i.
            expected_col0 = [0.1 * i for i in range(n_real)]
            np.testing.assert_allclose(ds[:, 0], expected_col0, atol=1e-9)

            # Time series should start at 0 (rebased) and end at (n_real-1)/50.
            times = f["nirs/data1/time"][...]
            assert times.shape == (n_real,)
            assert times[0] == 0.0
            assert abs(times[-1] - (n_real - 1) / 50.0) < 1e-9
    finally:
        if rec.is_recording:
            rec.stop()
        shutil.rmtree(root)


def test_stop_without_samples_does_not_create_snirf():
    root = tempfile.mkdtemp(prefix="fnirs_snirf_test_")
    try:
        rec = SessionRecorder(recordings_root=root)
        rec.start(
            "EmptySession_01",
            stream_info={"name": "Test", "type": "NIRS", "source_id": "TEST-001"},
            sample_rate=50.0,
            config_snapshot=_cfg_snapshot(),
        )
        rec.stop()
        snirf_path = os.path.join(rec.session_folder, "session.snirf")
        assert not os.path.exists(snirf_path), "Empty session should not emit SNIRF"
    finally:
        if rec.is_recording:
            rec.stop()
        shutil.rmtree(root)
