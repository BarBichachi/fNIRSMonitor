"""
Minimal SNIRF v1.1 writer for the monitor's recordings.

Why not pysnirf2: pysnirf2 0.7.3 (latest as of 2026-05) crashes on import
under numpy 2.x because it references removed np.string_. The SNIRF spec is
a small HDF5 layout, so we write it directly with h5py instead.

Output is intended to round-trip through MNE-NIRS' mne.io.read_raw_snirf
and Homer3 / NIRS-KIT importers. We write the "processed concentration"
flavor (dataType=99999) so analysts can pick up O2Hb / HHb without re-running
MBLL.

Spec reference: https://github.com/fNIRS/snirf
"""

import datetime
from pathlib import Path
from typing import Sequence

import h5py
import numpy as np


SNIRF_FORMAT_VERSION = "1.1"

# Length unit string; SNIRF accepts "mm", "cm", "m". Our config stores
# interoptode distance in cm, so cm is the natural choice here.
LENGTH_UNIT = "cm"


def write_snirf(
    path: str | Path,
    o2hb: np.ndarray,
    hhb: np.ndarray,
    timestamps: Sequence[float],
    sample_rate_hz: float,
    metadata: dict,
) -> None:
    # o2hb, hhb: shape (n_samples, 8) - raw post-MBLL concentrations in uM.
    # timestamps: length n_samples, monotonic seconds (LSL clock).
    # metadata: the metadata.json dict (DPF, distance, channel names, etc).

    o2hb = np.asarray(o2hb, dtype=np.float64)
    hhb = np.asarray(hhb, dtype=np.float64)
    if o2hb.shape != hhb.shape:
        raise ValueError(f"o2hb/hhb shape mismatch: {o2hb.shape} vs {hhb.shape}")
    if o2hb.shape[1] != 8:
        raise ValueError(f"expected 8 channels, got {o2hb.shape[1]}")

    n_samples = o2hb.shape[0]
    if len(timestamps) != n_samples:
        raise ValueError(
            f"timestamps length {len(timestamps)} != samples {n_samples}"
        )

    times = np.asarray(timestamps, dtype=np.float64)
    # SNIRF time vector is relative to start-of-data; subtracting t0 keeps
    # absolute clock offsets out of the file.
    if times.size > 0:
        times = times - times[0]

    # Interleaved column order: [Ch0_HbO, Ch0_HbR, Ch1_HbO, Ch1_HbR, ...].
    n_channels = o2hb.shape[1]
    data_time_series = np.empty((n_samples, n_channels * 2), dtype=np.float64)
    for ch in range(n_channels):
        data_time_series[:, 2 * ch] = o2hb[:, ch]
        data_time_series[:, 2 * ch + 1] = hhb[:, ch]

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    with h5py.File(path, "w") as f:
        _write_string(f, "formatVersion", SNIRF_FORMAT_VERSION)
        nirs = f.create_group("nirs")
        _write_meta_data_tags(nirs, metadata)
        _write_probe(nirs, metadata)
        _write_data(nirs, data_time_series, times, sample_rate_hz)


# ---------- HDF5 helpers ----------


def _write_string(parent, name: str, value: str) -> None:
    # SNIRF strings are stored as variable-length UTF-8 datasets. h5py wants
    # this expressed via h5py.string_dtype().
    dt = h5py.string_dtype(encoding="utf-8")
    parent.create_dataset(name, data=np.array(value, dtype=dt))


def _write_string_array(parent, name: str, values: Sequence[str]) -> None:
    dt = h5py.string_dtype(encoding="utf-8")
    parent.create_dataset(name, data=np.array(list(values), dtype=dt))


# ---------- SNIRF sections ----------


def _write_meta_data_tags(nirs, metadata: dict) -> None:
    tags = nirs.create_group("metaDataTags")
    start_iso = metadata.get("start_time_iso") or datetime.datetime.now().isoformat()
    try:
        dt = datetime.datetime.fromisoformat(start_iso)
    except ValueError:
        dt = datetime.datetime.now()

    _write_string(tags, "SubjectID", str(metadata.get("subject_id", "subject")))
    _write_string(tags, "MeasurementDate", dt.strftime("%Y-%m-%d"))
    _write_string(tags, "MeasurementTime", dt.strftime("%H:%M:%S"))
    _write_string(tags, "LengthUnit", LENGTH_UNIT)
    _write_string(tags, "TimeUnit", "s")
    _write_string(tags, "FrequencyUnit", "Hz")


def _write_probe(nirs, metadata: dict) -> None:
    probe = nirs.create_group("probe")

    # OctaMon convention.
    wavelengths = np.array([760.0, 850.0], dtype=np.float64)
    probe.create_dataset("wavelengths", data=wavelengths)

    # 8 sources (Tx1..Tx8), 2 detectors (Rx1, Rx2). Positions are placeholder
    # 2D coordinates so the file passes basic SNIRF validation; analysts who
    # need accurate optode geometry should overwrite these from the OxySoft
    # optode template for the specific device.
    n_sources = 8
    source_pos = np.zeros((n_sources, 2), dtype=np.float64)
    # Lay sources out in a line for visual placeholder.
    for i in range(n_sources):
        source_pos[i] = (i * 2.0, 0.0)
    probe.create_dataset("sourcePos2D", data=source_pos)

    detector_pos = np.array([[3.0, 1.0], [11.0, 1.0]], dtype=np.float64)
    probe.create_dataset("detectorPos2D", data=detector_pos)

    _write_string_array(probe, "sourceLabels", [f"S{i + 1}" for i in range(n_sources)])
    _write_string_array(probe, "detectorLabels", ["D1", "D2"])


def _write_data(nirs, data_time_series: np.ndarray, times: np.ndarray, sample_rate_hz: float) -> None:
    data1 = nirs.create_group("data1")
    data1.create_dataset("dataTimeSeries", data=data_time_series.astype(np.float64))
    data1.create_dataset("time", data=times.astype(np.float64))

    # Each column of dataTimeSeries gets a measurementList entry. SNIRF stores
    # these as numbered subgroups: measurementList1, measurementList2, ...
    n_channels = data_time_series.shape[1] // 2
    col = 1
    for ch in range(n_channels):
        # Channel ch maps to source (ch + 1) and detector ((ch // 4) + 1)
        # under OctaMon convention.
        source_index = ch + 1
        detector_index = (ch // 4) + 1
        for species in ("HbO", "HbR"):
            grp = data1.create_group(f"measurementList{col}")
            grp.create_dataset("sourceIndex", data=np.int32(source_index))
            grp.create_dataset("detectorIndex", data=np.int32(detector_index))
            grp.create_dataset("wavelengthIndex", data=np.int32(1))
            grp.create_dataset("dataType", data=np.int32(99999))  # processed
            grp.create_dataset("dataTypeIndex", data=np.int32(1))
            _write_string(grp, "dataTypeLabel", species)
            col += 1
