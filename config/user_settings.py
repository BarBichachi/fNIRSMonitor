import json
from pathlib import Path
from typing import Optional

from utils.app_paths import settings_file
from config.schema import validate, SettingsValidationError


def load(path: Optional[Path] = None) -> dict:
    # Reads user settings JSON, validates known keys, drops unknown keys.
    # Returns {} if the file does not exist. Re-raises on malformed JSON or
    # validation errors so the caller can decide what to surface.
    path = path or settings_file()
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise SettingsValidationError(f"settings.json root must be a JSON object, got {type(raw).__name__}")

    return validate(raw)


def save(settings: dict, path: Optional[Path] = None) -> None:
    # Writes the given settings dict to disk after validation.
    # Phase 6 will use this from the Settings dialog.
    path = path or settings_file()
    validated = validate(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(validated, f, indent=2)
