# --- Application Information ---
APP_NAME = "fNIRS Cognitive Monitor"
APP_VERSION = "1.0.0"

# --- UI Configuration ---
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 800

# --- LSL & Data Configuration ---
SAMPLE_RATE = 10  # Hz

# --- Calibration Configuration ---
CALIBRATION_DURATION = 10  # seconds

# --- Alerting Configuration ---
ALERT_HISTORY_SECONDS = 10  # seconds

# --- Sound Asset Paths ---
ALERT_SOUND_PATH = "assets/cognitive_load_detected.wav"
NOMINAL_SOUND_PATH = "assets/system_nominal.wav"

# --- Hardware & Channel Configuration (OctaMon M) ---
STREAM_TYPE = "fNIRS"
# 8 physical channels total: 4 left (L1,..,L4), 4 right (R1,..,R4)
CHANNEL_NAMES = [f"{prefix}{i}" for prefix in ("L", "R") for i in range(1, 5)]
EXPECTED_PHYSICAL_CHANNELS = 8

# Incoming raw order per pair is assumed [850, 760]
WAVELENGTH_ORDER = ("850nm", "760nm")

# Raw-only enforcement
RAW_ALLOWED_LENGTHS = {16, 32}  # 16 = already 8×2λ, 32 = Rx1(8×2λ)+Rx2(8×2λ)
RAW_MIN_POS = 1e-6              # clamp to avoid log(0)

# Placeholders sometimes used by exports for inactive pairs
PLACEHOLDER_HI = 4.81625
PLACEHOLDER_LO = 0.02025
PLACEHOLDER_EPS = 0.02
PAIR_VARIANCE_THRESH = 1e-4     # minimum variance to consider a pair active

# --- MBLL Calculation Constants ---
DPF = 6.0
INTEROPTODE_DISTANCE = 3.5  # cm
EXTINCTION_COEFFICIENTS = {
    "760nm": {"O2Hb": 0.1555, "HHb": 0.4178},
    "850nm": {"O2Hb": 0.2465, "HHb": 0.1833},
}

# --- Signal Quality (stddev on wavelength-1 trace) ---
QUALITY_STD_LOWER = 2.0  # std below this → 'red', else 'green'