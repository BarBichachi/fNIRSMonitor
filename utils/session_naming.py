import os
import re
import datetime


def get_today_recordings_folder(recordings_root: str) -> str:
    # Returns today's recordings folder, creating it if necessary
    date_str = datetime.datetime.now().strftime("%d-%m-%Y")
    folder = os.path.abspath(os.path.join(recordings_root, date_str))
    os.makedirs(folder, exist_ok=True)
    return folder


def split_name_and_index(text: str) -> tuple[str, int | None]:
    # Returns ("SleepExperiment", 1) for "SleepExperiment_01"
    # Returns ("SleepExperiment", None) for "SleepExperiment"
    text = (text or "").strip()
    match = re.match(r"^(.*?)(?:_(\d+))?$", text)
    if not match:
        return text, None

    prefix = (match.group(1) or "").strip()
    idx_str = match.group(2)
    idx = int(idx_str) if idx_str else None
    return prefix, idx


def get_next_index_for_prefix(recordings_root: str, prefix: str) -> int:
    # Scans today's folder for existing recordings with the given prefix.
    # Recognizes both the post-Phase-1 layout (per-recording folder named
    # HH-MM-SS_<prefix>_NN) and the legacy flat-file layout (used before the
    # per-recording folder split).
    folder = get_today_recordings_folder(recordings_root)
    safe_prefix = re.escape(prefix)

    folder_pattern = re.compile(rf"^\d{{2}}-\d{{2}}-\d{{2}}_{safe_prefix}_(\d+)$", re.IGNORECASE)
    legacy_file_pattern = re.compile(rf"_{safe_prefix}_(\d+)_RawOD\.txt$", re.IGNORECASE)

    max_idx = 0
    for name in os.listdir(folder):
        full = os.path.join(folder, name)

        if os.path.isdir(full):
            match = folder_pattern.match(name)
        else:
            match = legacy_file_pattern.search(name) if name.lower().endswith("_rawod.txt") else None

        if match:
            idx = int(match.group(1))
            if idx > max_idx:
                max_idx = idx

    return max_idx + 1


def format_name(prefix: str, idx: int) -> str:
    # Formats the name as "SleepExperiment_01"
    return f"{prefix}_{idx:02d}"


# Characters Windows forbids in file/folder names, plus ASCII control chars.
ILLEGAL_NAME_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_session_name(name: str, fallback: str = "session") -> str:
    # Strips characters that are illegal in Windows file/folder names so a
    # user-typed recording name can never crash folder creation. Also trims
    # trailing dots and spaces (illegal as a Windows name ending) and falls
    # back to a default if nothing usable remains.
    cleaned = ILLEGAL_NAME_PATTERN.sub("", name or "")
    cleaned = cleaned.strip().rstrip(". ")
    return cleaned if cleaned else fallback