# Code-side defaults for the application.
# These are overridable per-user via settings.json (loaded by config/__init__.py).
# Do NOT mutate these values at runtime. Use the controller's runtime state instead.

from utils.app_paths import resource

# --- Application Information ---
APP_NAME = "fNIRS Cognitive Monitor"
APP_VERSION = "1.0.0"

# --- UI Configuration ---
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 800

# --- LSL & Data Configuration ---
# Initial Hz used only for buffer pre-allocation before the actual stream rate
# is detected. After connect, the detected stream rate takes over.
SAMPLE_RATE = 10

# --- Calibration Configuration ---
CALIBRATION_DURATION = 10  # seconds

# --- Alerting Configuration ---
ALERT_HISTORY_SECONDS = 10  # seconds

# --- Sound Asset Paths ---
ALERT_SOUND_PATH = resource("assets/cognitive_load_detected.wav")
NOMINAL_SOUND_PATH = resource("assets/system_nominal.wav")

# --- Hardware & Channel Configuration (OctaMon M) ---
STREAM_TYPE = "NIRS"
# 8 physical channels total: 4 left (L1..L4), 4 right (R1..R4).
CHANNEL_NAMES = [f"{prefix}{i}" for prefix in ("L", "R") for i in range(1, 5)]
EXPECTED_PHYSICAL_CHANNELS = 8

# Incoming raw order per pair is assumed [850, 760].
# Phase 2 will replace this assumption with stream-metadata-driven mapping.
WAVELENGTH_ORDER = ("850nm", "760nm")

# Placeholder values that OxySoft emits for inactive optode pairs.
PLACEHOLDER_HI = 4.81625
PLACEHOLDER_LO = 0.02025
PLACEHOLDER_EPS = 0.02
PAIR_VARIANCE_THRESH = 1e-4  # minimum variance to consider a pair active

# --- MBLL Calculation Constants ---
# Extinction coefficients (mM^-1 cm^-1) from Matcher et al. 1995,
# "Performance comparison of several published tissue near-infrared
# spectroscopy algorithms", Analytical Biochemistry 227:54-68.
# These are the canonical values used by MNE-NIRS, Homer3, and NIRS-KIT,
# which ensures future SNIRF-based interop produces consistent results.
#
# Replay against OxySoft 3.2.72's NOTRAW export shows our traces match
# OxySoft within ~10% (uniform scale offset, same shape and dynamics).
# OxySoft's exact internal coefficient table is not publicly documented;
# the residual ~10% is the gap between Matcher and OxySoft's choice.
# For relative deltaHb dynamics (which is what drives the alert pipeline),
# this offset is irrelevant. For absolute concentration matching with
# OxySoft NOTRAW exports, expect a uniform ~10% bias.
#
# Verified by tests/test_mbll_against_oxysoft.py.
DPF = 6.56
INTEROPTODE_DISTANCE = 3.5  # cm
EXTINCTION_COEFFICIENTS = {
    "760nm": {"O2Hb": 0.586, "HHb": 1.548},
    "850nm": {"O2Hb": 1.058, "HHb": 0.781},
}

# --- Signal Quality ---
# Per-channel evaluator runs three independent checks on the 850 nm OD trace
# over a rolling QUALITY_WINDOW_S seconds. Each check yields one point;
# 3 = green, 2 = yellow, <=1 = red.
#   - std must exceed QUALITY_STD_LOWER (rejects flat-lined / disconnected channels)
#   - coefficient of variation must be below QUALITY_CV_UPPER (rejects runaway channels)
#   - heartbeat peak in 0.8-2.0 Hz must exceed noise (2.5-5.0 Hz) by
#     QUALITY_HR_SNR_THRESHOLD (confirms skin coupling). FFT recomputed
#     every QUALITY_HR_RECOMPUTE_S to keep the per-sample cost low.
QUALITY_WINDOW_S = 5.0
QUALITY_HR_RECOMPUTE_S = 1.0
QUALITY_STD_LOWER = 0.005
QUALITY_CV_UPPER = 0.05
QUALITY_HR_SNR_THRESHOLD = 3.0

# --- Signal Conditioning ---
# Causal Butterworth bandpass applied per-channel to O2Hb/HHb after MBLL.
# 0.01 Hz highpass removes slow drift; 0.5 Hz lowpass removes Mayer waves
# (~0.1 Hz peak) and heart rate (~1 Hz). Standard for cognitive fNIRS.
# Filtered values feed display and alerts; raw post-MBLL values are recorded
# so analysts can re-filter offline with their own pipeline.
FILTER_HIGHPASS_HZ = 0.01
FILTER_LOWPASS_HZ = 0.5
FILTER_ORDER = 4

# --- Baseline Configuration ---
# "single_sample" matches OxySoft's default: the first non-placeholder OD
# sample becomes the baseline. Cheap and consistent with OxySoft NOTRAW.
# "window" buffers BASELINE_WINDOW_S of OD before emitting any deltas,
# trading initial latency for lower baseline noise. Research-grade option.
# A manual "Set Baseline" action recomputes baseline from the last
# BASELINE_WINDOW_S of buffered OD regardless of mode.
BASELINE_MODE = "single_sample"
BASELINE_WINDOW_S = 10
