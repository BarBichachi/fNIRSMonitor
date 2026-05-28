import os
from pathlib import Path


# Project root: this file lives at <root>/utils/app_paths.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def app_data_dir() -> Path:
    # Per-user writable directory for settings, logs, and other app state.
    # On Windows this is %LOCALAPPDATA%/fNIRS Monitor.
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base)
    else:
        root = Path.home() / ".local" / "share"

    path = root / "fNIRS Monitor"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    # Absolute path to the user settings JSON.
    return app_data_dir() / "settings.json"


def default_recordings_dir() -> Path:
    # Suggested default for the recordings root on first run.
    docs = Path.home() / "Documents"
    return docs / "fNIRS Monitor" / "Recordings"


def resource(relative_path: str) -> str:
    # Resolves a project-bundled asset (sounds, icons, etc) to an absolute path
    # regardless of the current working directory.
    return str((PROJECT_ROOT / relative_path).resolve())
