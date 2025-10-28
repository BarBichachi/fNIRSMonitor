# --- Application Information ---
APP_NAME = "fNIRS Cognitive Monitor"
APP_VERSION = "1.0.0"

# --- UI Configuration ---
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 800

# --- LSL & Data Configuration ---
SAMPLE_RATE = 50

# --- Calibration Configuration ---
CALIBRATION_DURATION = 10

# --- Alerting Configuration ---
ALERT_HISTORY_SECONDS = 10

# --- Sound Asset Paths ---
ALERT_SOUND_PATH = "assets/cognitive_load_detected.wav"
NOMINAL_SOUND_PATH = "assets/system_nominal.wav"

# --- Hardware & Channel Configuration ---
STREAM_TYPE = "fNIRS"
CHANNEL_NAMES = [f"{prefix}{i}" for prefix in ('L', 'R') for i in range(1, 5)]
PRESET_MARKERS = ["Task Start", "User Response", "Error"]

# --- MBLL Calculation Constants ---
DPF = 6.0
INTEROPTODE_DISTANCE = 3.5
EXTINCTION_COEFFICIENTS = {
    '760nm': {'O2Hb': 0.1555, 'HHb': 0.4178},
    '850nm': {'O2Hb': 0.2465, 'HHb': 0.1833}
}