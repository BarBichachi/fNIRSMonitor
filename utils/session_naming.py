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
    # Scans today's folder for existing files with the given prefix
    folder = get_today_recordings_folder(recordings_root)
    safe_prefix = re.escape(prefix)

    # Matches: dd-mm-yyyy_HH-MM-SS_<prefix>_01_RawOD.txt
    pattern = re.compile(rf"_{safe_prefix}_(\d+)_RawOD\.txt$", re.IGNORECASE)

    max_idx = 0
    for name in os.listdir(folder):
        if not name.lower().endswith("_rawod.txt"):
            continue

        match = pattern.search(name)
        if match:
            idx = int(match.group(1))
            if idx > max_idx:
                max_idx = idx

    return max_idx + 1


def format_name(prefix: str, idx: int) -> str:
    # Formats the name as "SleepExperiment_01"
    return f"{prefix}_{idx:02d}"