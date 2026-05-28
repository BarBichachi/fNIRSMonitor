import os
import json
import datetime
from typing import Optional, List

import config
from utils.recording_writer import RecordingWriter


# Event marker text used in TSV "Event" column and metadata when special things happen.
EVENT_NAN_DROP = "NAN"
EVENT_RESUMED_PREFIX = "RESUMED-after-"


class SessionRecorder:
    # Orchestrates a recording session: folder layout, headers, metadata,
    # pause/resume, notes. Actual disk I/O happens on a background thread
    # owned by RecordingWriter.

    def __init__(self, recordings_root: str = "./Recordings"):
        self.recordings_root = recordings_root

        # Set when a session is active.
        self.session_folder: Optional[str] = None
        self.file_base: Optional[str] = None
        self.raw_path: Optional[str] = None
        self.calc_path: Optional[str] = None
        self.metadata_path: Optional[str] = None

        self._raw_file = None
        self._calc_file = None
        self._writer = RecordingWriter()

        self.is_recording = False
        self.is_paused = False
        self.sample_index = 0
        self.start_time: Optional[datetime.datetime] = None

        # Identity of the stream this recording is tied to. Used by can_resume
        # to refuse resuming into a different source.
        self._stream_source_id: Optional[str] = None

    # ---------- Public lifecycle ----------

    def start(
        self,
        session_name: str,
        stream_info: dict,
        sample_rate: float,
        config_snapshot: dict,
    ) -> None:
        if self.is_recording:
            raise RuntimeError("Recording already in progress")

        self.start_time = datetime.datetime.now()
        date = self.start_time.strftime("%d-%m-%Y")
        time_str = self.start_time.strftime("%H-%M-%S")

        date_folder = os.path.join(self.recordings_root, date)
        os.makedirs(date_folder, exist_ok=True)

        # Each recording lives in its own folder so raw_od.tsv, calculated.tsv,
        # metadata.json, and (optional) notes.txt stay together as one atomic unit.
        session_folder_name = f"{time_str}_{session_name}"
        session_folder = self._get_safe_dir(os.path.join(date_folder, session_folder_name))
        os.makedirs(session_folder, exist_ok=True)

        self.session_folder = session_folder
        self.file_base = os.path.basename(session_folder)
        self.raw_path = os.path.join(session_folder, "raw_od.tsv")
        self.calc_path = os.path.join(session_folder, "calculated.tsv")
        self.metadata_path = os.path.join(session_folder, "metadata.json")

        self._raw_file = open(self.raw_path, "w", encoding="utf-8")
        self._calc_file = open(self.calc_path, "w", encoding="utf-8")

        self._write_raw_header(self._raw_file, stream_info, sample_rate, config_snapshot)
        self._write_calc_header(self._calc_file, stream_info, sample_rate, config_snapshot)
        self._write_metadata(stream_info, sample_rate, config_snapshot)

        self._writer.start(self._raw_file, self._calc_file)

        self.sample_index = 0
        self.is_recording = True
        self.is_paused = False
        self._stream_source_id = stream_info.get("source_id", "") or ""

    def write(
        self,
        od32: Optional[List[float]],
        o2hb: Optional[List[float]],
        hhb: Optional[List[float]],
        adc: int = 0,
        event: int = 0,
        dropped: bool = False,
    ) -> None:
        # Atomic per-sample write. Both files get a row at the same sample index.
        # If `dropped` is True, both rows carry sentinel values and event="NAN".
        # If `dropped` is False but o2hb/hhb are None (placeholder sample), the
        # calc row is sentinel-zero with the normal event value; raw row is real.
        if not self.is_recording or self.is_paused:
            return

        idx = self.sample_index
        raw_row = self._format_raw_row(idx, od32, adc, event, dropped)
        calc_row = self._format_calc_row(idx, o2hb, hhb, event, dropped)
        self._writer.enqueue(raw_row, calc_row)
        self.sample_index += 1

    def pause(self) -> None:
        # Marks the recording paused. Files stay open; writer thread keeps
        # draining anything still in its queue but stops accepting new rows.
        if not self.is_recording:
            return
        self.is_paused = True

    def resume(self, gap_ms: int) -> None:
        # Resumes a paused recording and writes an event-marker row so the
        # downstream analyst can see exactly where the stream interruption was.
        if not self.is_paused:
            return
        self.is_paused = False
        self._write_event_marker(f"{EVENT_RESUMED_PREFIX}{int(gap_ms)}ms")

    def can_resume(self, stream_info: dict) -> bool:
        # Only resume if we are paused and the incoming stream identity matches
        # what was originally being recorded. Otherwise the safe move is to stop
        # the old recording and start a new one.
        if not self.is_paused:
            return False
        incoming_id = (stream_info.get("source_id", "") or "")
        return incoming_id == self._stream_source_id and bool(incoming_id)

    def stop(self) -> None:
        if not self.is_recording:
            return
        try:
            self._writer.stop(timeout=5.0)
            if self._raw_file is not None:
                self._raw_file.close()
            if self._calc_file is not None:
                self._calc_file.close()
        finally:
            self._raw_file = None
            self._calc_file = None
            self.is_recording = False
            self.is_paused = False
            self.sample_index = 0
            self.start_time = None
            self._stream_source_id = None

    def write_notes(self, notes_text: str) -> None:
        # Writes the operator's notes alongside the recording.
        if not self.session_folder:
            return
        notes_path = os.path.join(self.session_folder, "notes.txt")
        with open(notes_path, "w", encoding="utf-8") as f:
            f.write(notes_text.strip() + "\n")

    @property
    def dropped_count(self) -> int:
        return self._writer.dropped_count

    # ---------- Row formatting ----------

    def _format_raw_row(
        self,
        idx: int,
        od32: Optional[List[float]],
        adc: int,
        event: int,
        dropped: bool,
    ) -> str:
        row = [str(idx)]
        if dropped or od32 is None or len(od32) != 32:
            row.extend("0.00000" for _ in range(32))
        else:
            row.extend(f"{v:.5f}" for v in od32)
        row.append(str(int(adc)))
        row.append(EVENT_NAN_DROP if dropped else str(int(event)))
        return "\t".join(row) + "\n"

    def _format_calc_row(
        self,
        idx: int,
        o2hb: Optional[List[float]],
        hhb: Optional[List[float]],
        event: int,
        dropped: bool,
    ) -> str:
        row = [str(idx)]
        if dropped or o2hb is None or hhb is None or len(o2hb) != 8 or len(hhb) != 8:
            for _ in range(8):
                row.append("0.0000")
                row.append("0.0000")
        else:
            for i in range(8):
                row.append(f"{o2hb[i]:.4f}")
                row.append(f"{hhb[i]:.4f}")
        row.append(EVENT_NAN_DROP if dropped else str(int(event)))
        return "\t".join(row) + "\n"

    def _write_event_marker(self, marker: str) -> None:
        # Event-marker rows look like a normal row but the OD/Hb columns are zeros
        # and the Event column carries the marker string. Matches the sample-index
        # cadence so the two files remain row-aligned.
        if not self.is_recording or not self._writer:
            return
        idx = self.sample_index
        raw_zeros = "\t".join("0.00000" for _ in range(32))
        calc_zeros = "\t".join("0.0000" for _ in range(16))
        raw_row = f"{idx}\t{raw_zeros}\t0\t{marker}\n"
        calc_row = f"{idx}\t{calc_zeros}\t{marker}\n"
        self._writer.enqueue(raw_row, calc_row)
        self.sample_index += 1

    # ---------- Headers ----------

    def _write_raw_header(self, f, stream_info, sample_rate, cfg):
        self._write_common_header(f, stream_info, sample_rate, cfg, export_kind="Raw OD")
        f.write("Legend:\n")
        f.write("Column 1: (Sample number)\n")
        for i in range(32):
            f.write(f"Column {i + 2}: OD{i + 1}\n")
        f.write("Column 34: ADC\n")
        f.write("Column 35: (Event)\n")
        self._write_column_index_row(f, 35)

    def _write_calc_header(self, f, stream_info, sample_rate, cfg):
        self._write_common_header(f, stream_info, sample_rate, cfg, export_kind="Calculated")
        f.write("Legend:\n")
        f.write("Column 1: (Sample number)\n")
        mapping = [
            ("Rx1 Tx1", 2),
            ("Rx1 Tx2", 4),
            ("Rx1 Tx3", 6),
            ("Rx1 Tx4", 8),
            ("Rx2 Tx5", 10),
            ("Rx2 Tx6", 12),
            ("Rx2 Tx7", 14),
            ("Rx2 Tx8", 16),
        ]
        for label, col in mapping:
            f.write(f"Column {col}: {label} O2Hb\n")
            f.write(f"Column {col + 1}: {label} HHb\n")
        f.write("Column 18: (Event)\n")
        self._write_column_index_row(f, 18)

    def _write_common_header(self, f, stream_info, sample_rate, cfg, export_kind: str):
        export_dt = self.start_time
        f.write(f"Export date:\t{export_dt.strftime('%d-%m-%Y')}\n")
        f.write(f"Export time:\t{export_dt.strftime('%H:%M:%S')}\n")
        f.write(f"Export kind:\t{export_kind}\n")

        name = stream_info.get("name", "")
        s_type = stream_info.get("type", "")
        source_id = stream_info.get("source_id", "")
        if name:
            f.write(f"Stream name:\t{name}\n")
        if s_type:
            f.write(f"Stream type:\t{s_type}\n")
        if source_id:
            f.write(f"Source ID:\t{source_id}\n")
        if sample_rate:
            f.write(f"Data rate (Hz):\t{sample_rate}\n")

        dpf = cfg.get("DPF", None)
        dist = cfg.get("INTEROPTODE_DISTANCE", None)
        if dpf is not None:
            f.write(f"DPF:\t{dpf}\n")
        if dist is not None:
            f.write(f"Interoptode distance (cm):\t{dist}\n")

        wl_order = cfg.get("WAVELENGTH_ORDER", None)
        if wl_order:
            f.write(f"Wavelength order:\t{wl_order}\n")

        ext = cfg.get("EXTINCTION_COEFFICIENTS", None)
        if ext:
            f.write("Extinction coefficients:\n")
            for wl, vals in ext.items():
                o2 = vals.get("O2Hb", "")
                hh = vals.get("HHb", "")
                f.write(f"\t{wl}:\tO2Hb={o2}\tHHb={hh}\n")

        ch_names = cfg.get("CHANNEL_NAMES", None)
        if ch_names:
            f.write("Channel names:\t" + ", ".join(ch_names) + "\n")

        f.write("\n")

    def _write_column_index_row(self, f, count: int):
        f.write("\t".join(str(i) for i in range(1, count + 1)) + "\n")

    # ---------- Metadata ----------

    def _write_metadata(self, stream_info, sample_rate, cfg) -> None:
        # Machine-readable companion to the TSV files. Whatever changes in cfg
        # over time, the recording stays self-describing.
        metadata = {
            "app_name": config.APP_NAME,
            "app_version": config.APP_VERSION,
            "start_time_iso": self.start_time.isoformat(),
            "sample_rate_hz": float(sample_rate) if sample_rate else None,
            "stream": {
                "name": stream_info.get("name", ""),
                "type": stream_info.get("type", ""),
                "source_id": stream_info.get("source_id", ""),
            },
            "mbll": {
                "DPF": cfg.get("DPF"),
                "interoptode_distance_cm": cfg.get("INTEROPTODE_DISTANCE"),
                "wavelength_order": list(cfg.get("WAVELENGTH_ORDER") or ()),
                "extinction_coefficients": cfg.get("EXTINCTION_COEFFICIENTS"),
            },
            "channels": cfg.get("CHANNEL_NAMES"),
            "files": {
                "raw_od": "raw_od.tsv",
                "calculated": "calculated.tsv",
                "notes": "notes.txt",
            },
        }
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    # ---------- Path helpers ----------

    def _get_safe_dir(self, path: str) -> str:
        # Returns a non-existing directory path by auto-incrementing suffix.
        if not os.path.exists(path):
            return path
        idx = 1
        while True:
            candidate = f"{path}_{idx:03d}"
            if not os.path.exists(candidate):
                return candidate
            idx += 1
