import datetime
import os
import tempfile
from pathlib import Path

import h5py
import numpy as np
import pytest

from utils.snirf_writer import write_snirf


def _basic_metadata() -> dict:
    return {
        "start_time_iso": datetime.datetime(2026, 5, 28, 14, 32, 15).isoformat(),
        "sample_rate_hz": 50.0,
        "stream": {"name": "Test", "type": "NIRS", "source_id": "TEST-001"},
        "dpf": 6.56,
        "interoptode_distance_cm": 3.5,
    }


def _tmp_snirf_path() -> Path:
    fd, path = tempfile.mkstemp(suffix=".snirf")
    os.close(fd)
    p = Path(path)
    p.unlink()
    return p


class TestStructure:
    def test_file_has_required_top_level_groups(self):
        path = _tmp_snirf_path()
        n = 100
        write_snirf(
            path,
            o2hb=np.zeros((n, 8)),
            hhb=np.zeros((n, 8)),
            timestamps=np.arange(n) / 50.0,
            sample_rate_hz=50.0,
            metadata=_basic_metadata(),
        )

        with h5py.File(path, "r") as f:
            assert "formatVersion" in f
            assert f["formatVersion"][()].decode("utf-8") == "1.1"
            assert "nirs" in f
            nirs = f["nirs"]
            for required in ("metaDataTags", "probe", "data1"):
                assert required in nirs, f"Missing {required}"
        path.unlink()

    def test_data_time_series_shape(self):
        path = _tmp_snirf_path()
        n = 250
        write_snirf(
            path,
            o2hb=np.zeros((n, 8)),
            hhb=np.zeros((n, 8)),
            timestamps=np.arange(n) / 50.0,
            sample_rate_hz=50.0,
            metadata=_basic_metadata(),
        )
        with h5py.File(path, "r") as f:
            ds = f["nirs/data1/dataTimeSeries"]
            assert ds.shape == (n, 16), ds.shape
            t = f["nirs/data1/time"]
            assert t.shape == (n,)
            assert t[0] == 0.0
        path.unlink()

    def test_interleaved_column_order(self):
        # First column should be Ch0 HbO, second Ch0 HbR, third Ch1 HbO, ...
        path = _tmp_snirf_path()
        n = 10
        o2 = np.arange(n * 8).reshape(n, 8).astype(float)
        hh = -np.arange(n * 8).reshape(n, 8).astype(float)
        write_snirf(
            path,
            o2hb=o2, hhb=hh,
            timestamps=np.arange(n) / 50.0,
            sample_rate_hz=50.0,
            metadata=_basic_metadata(),
        )
        with h5py.File(path, "r") as f:
            ds = f["nirs/data1/dataTimeSeries"][...]
        for ch in range(8):
            np.testing.assert_array_equal(ds[:, 2 * ch], o2[:, ch])
            np.testing.assert_array_equal(ds[:, 2 * ch + 1], hh[:, ch])
        path.unlink()

    def test_measurement_list_count(self):
        path = _tmp_snirf_path()
        n = 50
        write_snirf(
            path,
            o2hb=np.zeros((n, 8)),
            hhb=np.zeros((n, 8)),
            timestamps=np.arange(n) / 50.0,
            sample_rate_hz=50.0,
            metadata=_basic_metadata(),
        )
        with h5py.File(path, "r") as f:
            ml_keys = [k for k in f["nirs/data1"].keys() if k.startswith("measurementList")]
            assert len(ml_keys) == 16, ml_keys
            # Verify each carries the expected datasets.
            for k in ml_keys[:4]:
                grp = f[f"nirs/data1/{k}"]
                for required in ("sourceIndex", "detectorIndex", "wavelengthIndex",
                                  "dataType", "dataTypeIndex", "dataTypeLabel"):
                    assert required in grp, f"{k} missing {required}"
        path.unlink()


class TestProbe:
    def test_wavelengths(self):
        path = _tmp_snirf_path()
        n = 10
        write_snirf(
            path,
            o2hb=np.zeros((n, 8)),
            hhb=np.zeros((n, 8)),
            timestamps=np.arange(n) / 50.0,
            sample_rate_hz=50.0,
            metadata=_basic_metadata(),
        )
        with h5py.File(path, "r") as f:
            wl = f["nirs/probe/wavelengths"][...]
            assert list(wl) == [760.0, 850.0], wl
        path.unlink()

    def test_source_detector_labels(self):
        path = _tmp_snirf_path()
        n = 10
        write_snirf(
            path,
            o2hb=np.zeros((n, 8)),
            hhb=np.zeros((n, 8)),
            timestamps=np.arange(n) / 50.0,
            sample_rate_hz=50.0,
            metadata=_basic_metadata(),
        )
        with h5py.File(path, "r") as f:
            sources = [s.decode("utf-8") for s in f["nirs/probe/sourceLabels"][...]]
            detectors = [s.decode("utf-8") for s in f["nirs/probe/detectorLabels"][...]]
        assert sources == [f"S{i}" for i in range(1, 9)]
        assert detectors == ["D1", "D2"]
        path.unlink()


class TestMetaData:
    def test_units_and_date(self):
        path = _tmp_snirf_path()
        n = 10
        write_snirf(
            path,
            o2hb=np.zeros((n, 8)),
            hhb=np.zeros((n, 8)),
            timestamps=np.arange(n) / 50.0,
            sample_rate_hz=50.0,
            metadata=_basic_metadata(),
        )
        with h5py.File(path, "r") as f:
            tags = f["nirs/metaDataTags"]
            assert tags["LengthUnit"][()].decode("utf-8") == "cm"
            assert tags["TimeUnit"][()].decode("utf-8") == "s"
            assert tags["FrequencyUnit"][()].decode("utf-8") == "Hz"
            assert tags["MeasurementDate"][()].decode("utf-8") == "2026-05-28"
            assert tags["MeasurementTime"][()].decode("utf-8") == "14:32:15"
        path.unlink()


class TestValidation:
    def test_shape_mismatch_raises(self):
        path = _tmp_snirf_path()
        n = 10
        with pytest.raises(ValueError):
            write_snirf(
                path,
                o2hb=np.zeros((n, 8)),
                hhb=np.zeros((n, 4)),
                timestamps=np.arange(n) / 50.0,
                sample_rate_hz=50.0,
                metadata=_basic_metadata(),
            )

    def test_wrong_channel_count_raises(self):
        path = _tmp_snirf_path()
        n = 10
        with pytest.raises(ValueError):
            write_snirf(
                path,
                o2hb=np.zeros((n, 4)),
                hhb=np.zeros((n, 4)),
                timestamps=np.arange(n) / 50.0,
                sample_rate_hz=50.0,
                metadata=_basic_metadata(),
            )

    def test_timestamp_length_mismatch_raises(self):
        path = _tmp_snirf_path()
        n = 10
        with pytest.raises(ValueError):
            write_snirf(
                path,
                o2hb=np.zeros((n, 8)),
                hhb=np.zeros((n, 8)),
                timestamps=np.arange(5) / 50.0,
                sample_rate_hz=50.0,
                metadata=_basic_metadata(),
            )
