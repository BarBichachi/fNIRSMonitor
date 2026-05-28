"""
Replay test: run a real OxySoft RAW OD export through our MBLL pipeline and
compare the resulting O2Hb/HHb traces against OxySoft's own NOTRAW export.

This is the only test that proves the MBLL math (extinction coefficients,
wavelength order, channel mapping, baseline handling) actually matches the
device's official output. If this test passes, the monitor produces the same
deltaHb traces OxySoft would have produced from the same OD stream.

Reference data lives outside the repo (real subject data). Set the
FNIRS_REFERENCE_DATA env var to the folder containing the .txt files, or use
the default location below. The test is skipped if files are not found.
"""

import os
from pathlib import Path

import numpy as np
import pytest

from logic.data_processor import DataProcessor


DEFAULT_REFERENCE_DIR = Path(r"C:\Users\BARBIC\Desktop\Work\fNIRS\oxysoft 3.2.72")
RAW_FILE = "1127_2025_Experiment.txt"
NOTRAW_FILE = "1127_2025_ExperimentNOTRAW.txt"

# Number of samples to replay. 600 samples @ 50 Hz = 12 s, enough to exercise
# the math without making the test slow.
N_SAMPLES = 600

# Thresholds (per the Phase 2 plan): per-sample RMSE and worst-case error,
# in micromolar, computed across all 16 traces (8 O2Hb + 8 HHb).
RMSE_THRESHOLD_UM = 0.05
MAX_ABS_ERROR_THRESHOLD_UM = 0.5


def _reference_dir() -> Path:
    override = os.environ.get("FNIRS_REFERENCE_DATA")
    return Path(override) if override else DEFAULT_REFERENCE_DIR


def _skip_if_missing() -> Path:
    ref_dir = _reference_dir()
    raw = ref_dir / RAW_FILE
    notraw = ref_dir / NOTRAW_FILE
    if not raw.exists() or not notraw.exists():
        pytest.skip(
            f"OxySoft reference files not found under {ref_dir}. "
            f"Set FNIRS_REFERENCE_DATA to the folder containing {RAW_FILE} and {NOTRAW_FILE}."
        )
    return ref_dir


def _parse_oxysoft_table(path: Path, n_data_cols_expected: int) -> np.ndarray:
    # OxySoft export format: a free-form text header, then a single
    # column-index row (1\t2\t3...), then data rows.
    # We detect the start of data by finding the column-index row.
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        seen_col_idx = False
        for raw_line in f:
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            if not stripped:
                continue
            cells = stripped.split()
            # Column-index row: all integers in strictly increasing order from 1.
            if not seen_col_idx:
                try:
                    nums = [int(c) for c in cells]
                except ValueError:
                    continue
                if nums and nums == list(range(1, len(nums) + 1)):
                    seen_col_idx = True
                continue
            try:
                values = [float(c) for c in cells]
            except ValueError:
                continue
            rows.append(values)
            if len(rows) >= N_SAMPLES + 1:  # +1 for OxySoft's sample-0 row
                break

    if not rows:
        raise RuntimeError(f"Could not parse data rows from {path}")
    arr = np.array(rows, dtype=float)
    # First column is OxySoft's sample number; trim it.
    arr = arr[:, 1:]
    # Expected width = data columns we care about + optional ADC + Event.
    if arr.shape[1] < n_data_cols_expected:
        raise RuntimeError(
            f"Expected at least {n_data_cols_expected} data columns in {path.name}, "
            f"got {arr.shape[1]}"
        )
    return arr


def _replay_raw_through_pipeline(raw_array: np.ndarray) -> np.ndarray:
    # raw_array: (N, >=32) with the 32 OD columns first.
    # Returns: (N_used, 16) where each row is [O2Hb_ch0..7, HHb_ch0..7] in uM,
    # with the first sample being the baseline reference (delta=0).
    dp = DataProcessor()
    dp.set_sample_rate(50.0)

    od_columns = raw_array[:, :32]

    o2_rows = []
    hh_rows = []
    for i in range(od_columns.shape[0]):
        od_sample = od_columns[i, :].tolist()
        processed = dp.process_sample_od(od_sample, alert_rules={"threshold": 1e9, "duration": 1})
        if processed is None:
            # Placeholder-only sample (all 4.81625); skip.
            continue
        o2_rows.append(processed["O2Hb"])
        hh_rows.append(processed["HHb"])

    o2 = np.array(o2_rows, dtype=float)
    hh = np.array(hh_rows, dtype=float)
    return np.concatenate([o2, hh], axis=1)  # shape (N_used, 16)


def _parse_notraw_traces(notraw_array: np.ndarray) -> np.ndarray:
    # notraw_array: (N, >=16) where columns are interleaved
    # [Ch0_O2Hb, Ch0_HHb, Ch1_O2Hb, Ch1_HHb, ..., Ch7_O2Hb, Ch7_HHb].
    # Returns: (N, 16) with the same [O2Hb_ch0..7, HHb_ch0..7] layout as our output.
    interleaved = notraw_array[:, :16]
    o2 = interleaved[:, 0::2]
    hh = interleaved[:, 1::2]
    return np.concatenate([o2, hh], axis=1)


@pytest.fixture(scope="module")
def replay_traces():
    ref_dir = _skip_if_missing()
    raw_path = ref_dir / RAW_FILE
    notraw_path = ref_dir / NOTRAW_FILE

    raw = _parse_oxysoft_table(raw_path, n_data_cols_expected=32)
    notraw = _parse_oxysoft_table(notraw_path, n_data_cols_expected=16)

    ours_with_baseline = _replay_raw_through_pipeline(raw)
    theirs_aligned = _parse_notraw_traces(notraw)

    # Skip OxySoft's sample-0 row (the absolute reference, not a delta) and
    # truncate both to the smaller usable length.
    theirs = theirs_aligned[1:]
    n = min(ours_with_baseline.shape[0], theirs.shape[0])
    ours = ours_with_baseline[:n]
    theirs = theirs[:n]

    # Re-baseline both to their own first row so any constant offset between
    # OxySoft's internal baseline and ours falls out of the comparison.
    ours_rebased = ours - ours[0:1, :]
    theirs_rebased = theirs - theirs[0:1, :]

    return ours_rebased, theirs_rebased


def test_replay_rmse_within_threshold(replay_traces):
    ours, theirs = replay_traces
    diff = ours - theirs
    rmse_per_channel = np.sqrt(np.mean(diff ** 2, axis=0))
    overall_rmse = float(np.sqrt(np.mean(diff ** 2)))

    print()
    print(f"Replay length: {ours.shape[0]} samples")
    print(f"Per-channel RMSE (uM): {np.round(rmse_per_channel, 4).tolist()}")
    print(f"Overall RMSE (uM):     {overall_rmse:.4f}")

    assert overall_rmse < RMSE_THRESHOLD_UM, (
        f"Overall RMSE {overall_rmse:.4f} uM exceeds threshold "
        f"{RMSE_THRESHOLD_UM} uM. Per-channel: {rmse_per_channel.tolist()}"
    )


def test_replay_max_abs_error_within_threshold(replay_traces):
    ours, theirs = replay_traces
    diff = np.abs(ours - theirs)
    max_per_channel = np.max(diff, axis=0)
    overall_max = float(np.max(diff))

    print()
    print(f"Per-channel max |error| (uM): {np.round(max_per_channel, 4).tolist()}")
    print(f"Overall max |error| (uM):     {overall_max:.4f}")

    assert overall_max < MAX_ABS_ERROR_THRESHOLD_UM, (
        f"Max absolute error {overall_max:.4f} uM exceeds threshold "
        f"{MAX_ABS_ERROR_THRESHOLD_UM} uM. Per-channel: {max_per_channel.tolist()}"
    )
