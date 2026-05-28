# Configuration entry point. Imports defaults, overlays user settings, exposes
# everything at module level so existing `import config; config.DPF` keeps working.
#
# Important: do NOT mutate these module-level values at runtime. Runtime state
# (e.g. the detected sample rate) belongs on the controller / data processor.
# Settings changes from the UI (Phase 6) go through config.reload() after save.

from config import defaults as _defaults
from config import user_settings as _user_settings

# Re-export every public name from defaults at module level.
for _name in dir(_defaults):
    if _name.startswith("_"):
        continue
    globals()[_name] = getattr(_defaults, _name)


def reload() -> None:
    # Re-reads defaults and overlays user settings.json. Phase 6 calls this
    # after the Settings dialog saves.
    for _name in dir(_defaults):
        if _name.startswith("_"):
            continue
        globals()[_name] = getattr(_defaults, _name)

    try:
        overrides = _user_settings.load()
    except Exception as exc:
        # Bad settings.json should not crash the app; defaults remain in effect.
        # Note: this can run before the logging system is initialised, so we
        # fall back to stderr in that case. The main module wires logging up
        # almost immediately after import.
        import logging
        _log = logging.getLogger(__name__)
        if _log.hasHandlers() or logging.getLogger().hasHandlers():
            _log.error("config.reload: failed to load user settings (%s); using defaults.", exc)
        else:
            import sys
            print(f"config.reload: failed to load user settings ({exc}); using defaults.",
                  file=sys.stderr)
        return

    for key, value in overrides.items():
        globals()[key] = value


# Apply user overrides at import time.
reload()
