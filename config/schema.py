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


@_register("RECORDINGS_ROOT")
def _validate_recordings_root(value: Any) -> str:
    value = str(value)
    if not value.strip():
        raise SettingsValidationError("RECORDINGS_ROOT must be a non-empty path")
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
