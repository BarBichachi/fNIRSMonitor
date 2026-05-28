from typing import Any


class SettingsValidationError(ValueError):
    pass


# Whitelist of keys the user may override via settings.json, with validators.
# Anything not in this map is ignored on load.
_VALIDATORS = {}


def _register(key: str):
    def deco(func):
        _VALIDATORS[key] = func
        return func
    return deco


@_register("DPF")
def _validate_dpf(value: Any) -> float:
    value = float(value)
    if not (1.0 <= value <= 12.0):
        raise SettingsValidationError(f"DPF must be in [1.0, 12.0], got {value}")
    return value


@_register("INTEROPTODE_DISTANCE")
def _validate_distance(value: Any) -> float:
    value = float(value)
    if not (0.5 <= value <= 10.0):
        raise SettingsValidationError(
            f"INTEROPTODE_DISTANCE (cm) must be in [0.5, 10.0], got {value}"
        )
    return value


@_register("EXTINCTION_COEFFICIENTS")
def _validate_coefficients(value: Any) -> dict:
    if not isinstance(value, dict):
        raise SettingsValidationError("EXTINCTION_COEFFICIENTS must be a mapping")

    for wl, pair in value.items():
        if not isinstance(pair, dict):
            raise SettingsValidationError(
                f"EXTINCTION_COEFFICIENTS[{wl!r}] must be a mapping of species -> float"
            )
        for species in ("O2Hb", "HHb"):
            if species not in pair:
                raise SettingsValidationError(
                    f"EXTINCTION_COEFFICIENTS[{wl!r}] missing {species!r}"
                )
            float(pair[species])  # raises if not numeric

    return value


@_register("WAVELENGTH_ORDER")
def _validate_wavelength_order(value: Any) -> tuple:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise SettingsValidationError("WAVELENGTH_ORDER must be a 2-element sequence")
    return tuple(str(v) for v in value)


@_register("BASELINE_MODE")
def _validate_baseline_mode(value: Any) -> str:
    value = str(value)
    valid = ("single_sample", "window")
    if value not in valid:
        raise SettingsValidationError(
            f"BASELINE_MODE must be one of {valid}, got {value!r}"
        )
    return value


@_register("BASELINE_WINDOW_S")
def _validate_baseline_window_s(value: Any) -> float:
    value = float(value)
    if not (1.0 <= value <= 120.0):
        raise SettingsValidationError(
            f"BASELINE_WINDOW_S must be in [1.0, 120.0], got {value}"
        )
    return value


@_register("FILTER_HIGHPASS_HZ")
def _validate_filter_highpass(value: Any) -> float:
    value = float(value)
    if not (0.0 < value < 5.0):
        raise SettingsValidationError(
            f"FILTER_HIGHPASS_HZ must be in (0, 5), got {value}"
        )
    return value


@_register("FILTER_LOWPASS_HZ")
def _validate_filter_lowpass(value: Any) -> float:
    value = float(value)
    if not (0.05 <= value <= 50.0):
        raise SettingsValidationError(
            f"FILTER_LOWPASS_HZ must be in [0.05, 50.0], got {value}"
        )
    return value


@_register("FILTER_ORDER")
def _validate_filter_order(value: Any) -> int:
    value = int(value)
    if not (1 <= value <= 10):
        raise SettingsValidationError(
            f"FILTER_ORDER must be in [1, 10], got {value}"
        )
    return value


@_register("QUALITY_WINDOW_S")
def _validate_quality_window_s(value: Any) -> float:
    value = float(value)
    if not (1.0 <= value <= 60.0):
        raise SettingsValidationError(
            f"QUALITY_WINDOW_S must be in [1.0, 60.0], got {value}"
        )
    return value


@_register("QUALITY_HR_RECOMPUTE_S")
def _validate_quality_hr_recompute_s(value: Any) -> float:
    value = float(value)
    if not (0.1 <= value <= 10.0):
        raise SettingsValidationError(
            f"QUALITY_HR_RECOMPUTE_S must be in [0.1, 10.0], got {value}"
        )
    return value


@_register("QUALITY_STD_LOWER")
def _validate_quality_std_lower(value: Any) -> float:
    value = float(value)
    if not (0.0 < value < 1.0):
        raise SettingsValidationError(
            f"QUALITY_STD_LOWER must be in (0.0, 1.0), got {value}"
        )
    return value


@_register("QUALITY_CV_UPPER")
def _validate_quality_cv_upper(value: Any) -> float:
    value = float(value)
    if not (0.0 < value < 10.0):
        raise SettingsValidationError(
            f"QUALITY_CV_UPPER must be in (0.0, 10.0), got {value}"
        )
    return value


@_register("QUALITY_HR_SNR_THRESHOLD")
def _validate_quality_hr_snr_threshold(value: Any) -> float:
    value = float(value)
    if not (1.0 <= value <= 100.0):
        raise SettingsValidationError(
            f"QUALITY_HR_SNR_THRESHOLD must be in [1.0, 100.0], got {value}"
        )
    return value


@_register("RECONNECT_TOLERANCE_S")
def _validate_reconnect_tolerance_s(value: Any) -> float:
    value = float(value)
    if not (0.5 <= value <= 60.0):
        raise SettingsValidationError(
            f"RECONNECT_TOLERANCE_S must be in [0.5, 60.0], got {value}"
        )
    return value


@_register("SOUND_NOMINAL_SUPPRESS_S")
def _validate_sound_nominal_suppress_s(value: Any) -> float:
    value = float(value)
    if not (0.0 <= value <= 60.0):
        raise SettingsValidationError(
            f"SOUND_NOMINAL_SUPPRESS_S must be in [0.0, 60.0], got {value}"
        )
    return value


@_register("LOAD_DETECTOR_REST_WINDOW_S")
def _validate_load_detector_rest_window_s(value: Any) -> float:
    value = float(value)
    if not (10.0 <= value <= 600.0):
        raise SettingsValidationError(
            f"LOAD_DETECTOR_REST_WINDOW_S must be in [10.0, 600.0], got {value}"
        )
    return value


@_register("LOAD_DETECTOR_ACTIVE_WINDOW_S")
def _validate_load_detector_active_window_s(value: Any) -> float:
    value = float(value)
    if not (1.0 <= value <= 300.0):
        raise SettingsValidationError(
            f"LOAD_DETECTOR_ACTIVE_WINDOW_S must be in [1.0, 300.0], got {value}"
        )
    return value


@_register("LOAD_DETECTOR_K_SD")
def _validate_load_detector_k_sd(value: Any) -> float:
    value = float(value)
    if not (0.1 <= value <= 10.0):
        raise SettingsValidationError(
            f"LOAD_DETECTOR_K_SD must be in [0.1, 10.0], got {value}"
        )
    return value


@_register("LOAD_DETECTOR_MIN_ELEVATED_CHANNELS")
def _validate_load_detector_min_elevated_channels(value: Any) -> int:
    value = int(value)
    if not (1 <= value <= 4):
        raise SettingsValidationError(
            f"LOAD_DETECTOR_MIN_ELEVATED_CHANNELS must be in [1, 4], got {value}"
        )
    return value


@_register("LOAD_DETECTOR_HHB_TOL_UM")
def _validate_load_detector_hhb_tol_um(value: Any) -> float:
    value = float(value)
    if not (0.0 <= value <= 10.0):
        raise SettingsValidationError(
            f"LOAD_DETECTOR_HHB_TOL_UM must be in [0.0, 10.0], got {value}"
        )
    return value


@_register("RECORDINGS_ROOT")
def _validate_recordings_root(value: Any) -> str:
    # None = use platform default. Otherwise non-empty string path.
    if value is None:
        return None
    value = str(value)
    if not value.strip():
        raise SettingsValidationError("RECORDINGS_ROOT must be a non-empty path")
    return value


def validate(raw: dict) -> dict:
    # Returns a dict of validated overrides. Unknown keys are dropped with no error.
    # Invalid known keys raise SettingsValidationError.
    out = {}
    for key, value in (raw or {}).items():
        validator = _VALIDATORS.get(key)
        if validator is None:
            continue
        out[key] = validator(value)
    return out
