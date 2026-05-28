"""
Diagnostic for the MBLL replay mismatch. Prints first few samples of OxySoft's
NOTRAW alongside ours, ratios, and tries a few candidate coefficient sets.
"""

import os
import sys
from pathlib import Path

import numpy as np

# Allow `import config` etc. when run as a script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from logic.data_processor import DataProcessor


DEFAULT_REFERENCE_DIR = Path(r"C:\Users\BARBIC\Desktop\Work\fNIRS\oxysoft 3.2.72")
RAW_FILE = "1127_2025_Experiment.txt"
NOTRAW_FILE = "1127_2025_ExperimentNOTRAW.txt"


def parse_oxysoft_table(path: Path, n_samples: int) -> np.ndarray:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        seen_col_idx = False
        for raw_line in f:
            stripped = raw_line.strip()
            if not stripped:
                continue
            cells = stripped.split()
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
            if len(rows) >= n_samples + 1:
                break
    arr = np.array(rows, dtype=float)
    return arr[:, 1:]  # drop sample column


def replay_with_coefficients(raw_array: np.ndarray, ext_coefs: dict, dpf: float, distance: float) -> np.ndarray:
    # Patch config so DataProcessor picks up our trial coefficients.
    config.EXTINCTION_COEFFICIENTS = ext_coefs
    config.DPF = dpf
    config.INTEROPTODE_DISTANCE = distance

    dp = DataProcessor()
    dp.set_sample_rate(50.0)

    od_columns = raw_array[:, :32]
    o2_rows, hh_rows = [], []
    for i in range(od_columns.shape[0]):
        processed = dp.process_sample_od(od_columns[i].tolist(), alert_rules={"threshold": 1e9, "duration": 1})
        if processed is None:
            continue
        o2_rows.append(processed["O2Hb"])
        hh_rows.append(processed["HHb"])
    return np.concatenate([np.array(o2_rows), np.array(hh_rows)], axis=1)


def parse_notraw_traces(arr: np.ndarray) -> np.ndarray:
    inter = arr[:, :16]
    return np.concatenate([inter[:, 0::2], inter[:, 1::2]], axis=1)


def rmse_per_channel(ours: np.ndarray, theirs: np.ndarray) -> np.ndarray:
    diff = ours - theirs
    return np.sqrt(np.mean(diff ** 2, axis=0))


def evaluate(label: str, raw, notraw_traces, ext, dpf, dist, n_print=4):
    print(f"\n=== {label}: DPF={dpf}, dist={dist}, eps={ext} ===")
    ours_full = replay_with_coefficients(raw, ext, dpf, dist)
    # Skip OxySoft sample 0 (absolute reference); align lengths; re-baseline both.
    theirs = notraw_traces[1:]
    n = min(ours_full.shape[0], theirs.shape[0])
    ours = ours_full[:n] - ours_full[0:1, :]
    theirs = theirs[:n] - theirs[0:1, :]

    rmse = rmse_per_channel(ours, theirs)
    print(f"Per-channel RMSE (uM): {np.round(rmse, 4).tolist()}")
    print(f"Overall RMSE: {np.sqrt(np.mean((ours-theirs)**2)):.4f}")

    print("\nFirst {} sample comparison for Ch0..Ch7 O2Hb (theirs / ours / ratio):".format(n_print))
    for s in range(1, n_print + 1):
        line = []
        for ch in range(8):
            t = theirs[s, ch]
            o = ours[s, ch]
            ratio = (t / o) if abs(o) > 1e-9 else float("inf")
            line.append(f"Ch{ch}: {t:+.4f}/{o:+.4f}={ratio:+.3f}")
        print(f" s={s}: " + " ".join(line))


def main():
    ref_dir = Path(os.environ.get("FNIRS_REFERENCE_DATA", DEFAULT_REFERENCE_DIR))
    raw = parse_oxysoft_table(ref_dir / RAW_FILE, n_samples=300)
    notraw = parse_oxysoft_table(ref_dir / NOTRAW_FILE, n_samples=300)
    theirs_traces = parse_notraw_traces(notraw)

    print("RAW shape:", raw.shape)
    print("NOTRAW shape:", notraw.shape)
    print("NOTRAW first row (the absolute reference, should be large):")
    print(" ", notraw[0, :17])

    # Trial 1: current coefficients
    evaluate(
        "Current (defaults)",
        raw, theirs_traces,
        ext={"760nm": {"O2Hb": 0.2178, "HHb": 0.5971},
             "850nm": {"O2Hb": 0.4459, "HHb": 0.3003}},
        dpf=6.56, dist=3.5,
    )

    # Trial 2: Cope & Delpy 1988-style (Matcher 1995 values, log10 mM-1 cm-1)
    evaluate(
        "Matcher 1995",
        raw, theirs_traces,
        ext={"760nm": {"O2Hb": 0.586, "HHb": 1.548},
             "850nm": {"O2Hb": 1.058, "HHb": 0.781}},
        dpf=6.56, dist=3.5,
    )

    # Trial 3: Cope thesis original
    evaluate(
        "Cope 1991",
        raw, theirs_traces,
        ext={"760nm": {"O2Hb": 0.5854, "HHb": 1.5483},
             "850nm": {"O2Hb": 1.0507, "HHb": 0.7929}},
        dpf=6.56, dist=3.5,
    )

    # Trial 4: Wray 1988 (alternative)
    evaluate(
        "Wray 1988",
        raw, theirs_traces,
        ext={"760nm": {"O2Hb": 0.5860, "HHb": 1.5489},
             "850nm": {"O2Hb": 1.0496, "HHb": 0.7861}},
        dpf=6.56, dist=3.5,
    )

    # Trial 5: maybe DPF differs? Try 4.0
    evaluate(
        "Cope + DPF=4.0",
        raw, theirs_traces,
        ext={"760nm": {"O2Hb": 0.5854, "HHb": 1.5483},
             "850nm": {"O2Hb": 1.0507, "HHb": 0.7929}},
        dpf=4.0, dist=3.5,
    )


if __name__ == "__main__":
    main()
