import os
import datetime
from typing import Optional, List


class SessionRecorder:
    # Handles session recording to OxySoft-style TXT files (Raw OD + Calculated data)

    def __init__(self, recordings_root: str = "./Recordings"):
        # Initializes the recorder without starting a session
        self.m_RecordingsRoot = recordings_root
        self.m_SessionFolder = None

        self.m_RawFile = None
        self.m_CalcFile = None

        self.m_IsRecording = False
        self.m_SampleIndex = 0
        self.m_StartTime = None

    # ---------- Public API ----------

    def start(self, session_name: str, stream_info: dict, sample_rate: float, config_snapshot: dict):
        # Starts a new recording session and opens both output files
        if self.m_IsRecording:
            raise RuntimeError("Recording already in progress")

        self.m_StartTime = datetime.datetime.now()
        date = self.m_StartTime.strftime("%d-%m-%Y")
        time = self.m_StartTime.strftime("%H-%M-%S")
        self.m_SessionFolder = os.path.join(self.m_RecordingsRoot, date)
        os.makedirs(self.m_SessionFolder, exist_ok=True)

        file_name = f"{date}_{time}_{session_name}"
        raw_path = self._get_safe_path(os.path.join(self.m_SessionFolder, f"{file_name}_RawOD.txt"))
        calc_path = self._get_safe_path(os.path.join(self.m_SessionFolder, f"{file_name}_Calculated.txt"))

        self.m_RawFile = open(raw_path, "w", encoding="utf-8")
        self.m_CalcFile = open(calc_path, "w", encoding="utf-8")

        self._write_raw_header(self.m_RawFile, stream_info, sample_rate, config_snapshot)
        self._write_calc_header(self.m_CalcFile, stream_info, sample_rate, config_snapshot)

        self.m_SampleIndex = 0
        self.m_IsRecording = True

    def write_raw(self, od32: List[float], adc: int = 0, event: int = 0):
        # Writes one raw sample row (OD32 + ADC + Event)
        if not self.m_IsRecording:
            return

        row = [str(self.m_SampleIndex)]
        row.extend(f"{v:.5f}" for v in od32)
        row.append(str(adc))
        row.append(str(event))

        self.m_RawFile.write("\t".join(row) + "\n")
        self.m_RawFile.flush()

    def write_calculated(self,
                         o2hb: Optional[List[float]],
                         hhb: Optional[List[float]],
                         event: int = 0):
        # Writes one calculated sample row (O2Hb/HHb or zeros if missing)
        if not self.m_IsRecording:
            return

        row = [str(self.m_SampleIndex)]

        if o2hb is None or hhb is None:
            # Placeholder row (processed=None)
            for _ in range(8):
                row.append("0")
                row.append("0")
        else:
            for i in range(8):
                row.append(f"{o2hb[i]:.4f}")
                row.append(f"{hhb[i]:.4f}")

        row.append(str(event))
        self.m_CalcFile.write("\t".join(row) + "\n")
        self.m_CalcFile.flush()

        self.m_SampleIndex += 1

    def stop(self):
        # Stops recording and closes files safely
        if not self.m_IsRecording:
            return

        try:
            if self.m_RawFile:
                self.m_RawFile.flush()
                self.m_RawFile.close()
            if self.m_CalcFile:
                self.m_CalcFile.flush()
                self.m_CalcFile.close()
        finally:
            self.m_RawFile = None
            self.m_CalcFile = None
            self.m_IsRecording = False
            self.m_SampleIndex = 0
            self.m_StartTime = None

    @property
    def is_recording(self) -> bool:
        return self.m_IsRecording

    # ---------- Internal helpers ----------

    def _get_safe_path(self, path: str) -> str:
        # Returns a non-existing path by auto-incrementing suffix if needed
        if not os.path.exists(path):
            return path

        base, ext = os.path.splitext(path)
        idx = 1
        while True:
            candidate = f"{base}_{idx:03d}{ext}"
            if not os.path.exists(candidate):
                return candidate
            idx += 1

    def _write_raw_header(self, f, stream_info, sample_rate, cfg):
        # Writes OxySoft-like header for raw OD export
        self._write_common_header(f, stream_info, sample_rate, cfg, export_kind="Raw OD")
        f.write("Legend:\n")
        f.write("Column 1: (Sample number)\n")

        # Keep generic OD1..OD32 labels (we don't actually know the exact optode text mapping from stream)
        for i in range(32):
            f.write(f"Column {i + 2}: OD{i + 1}\n")

        f.write("Column 34: ADC\n")
        f.write("Column 35: (Event)\n")
        self._write_column_index_row(f, 35)

    def _write_calc_header(self, f, stream_info, sample_rate, cfg):
        # Writes OxySoft-like header for calculated Hb export
        self._write_common_header(f, stream_info, sample_rate, cfg, export_kind="Calculated")
        f.write("Legend:\n")
        f.write("Column 1: (Sample number)\n")

        # Match the Rx/Tx naming style from your Experiment3:
        # Rx1 Tx1..Tx4, then Rx2 Tx5..Tx8
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
        # Writes shared header information in an OxySoft-like style (only real known values)
        export_dt = self.m_StartTime
        f.write(f"Export date:\t{export_dt.strftime('%d-%m-%Y')}\n")
        f.write(f"Export time:\t{export_dt.strftime('%H:%M:%S')}\n")
        f.write(f"Export kind:\t{export_kind}\n")

        name = stream_info.get('name', '')
        s_type = stream_info.get('type', '')
        source_id = stream_info.get('source_id', '')

        if name:
            f.write(f"Stream name:\t{name}\n")
        if s_type:
            f.write(f"Stream type:\t{s_type}\n")
        if source_id:
            f.write(f"Source ID:\t{source_id}\n")

        if sample_rate:
            f.write(f"Data rate (Hz):\t{sample_rate}\n")

        # Config-derived parameters (allowed and real)
        dpf = cfg.get('DPF', None)
        dist = cfg.get('INTEROPTODE_DISTANCE', None)
        if dpf is not None:
            f.write(f"DPF:\t{dpf}\n")
        if dist is not None:
            f.write(f"Interoptode distance (cm):\t{dist}\n")

        # Optional additional scientific config, if provided
        wl_order = cfg.get('WAVELENGTH_ORDER', None)
        if wl_order:
            f.write(f"Wavelength order:\t{wl_order}\n")

        ext = cfg.get('EXTINCTION_COEFFICIENTS', None)
        if ext:
            f.write("Extinction coefficients:\n")
            try:
                for wl, vals in ext.items():
                    o2 = vals.get("O2Hb", "")
                    hh = vals.get("HHb", "")
                    f.write(f"\t{wl}:\tO2Hb={o2}\tHHb={hh}\n")
            except Exception:
                pass

        ch_names = cfg.get('CHANNEL_NAMES', None)
        if ch_names:
            f.write("Channel names:\t" + ", ".join(ch_names) + "\n")

        f.write("\n")

    def _write_column_index_row(self, f, count: int):
        # Writes the column index row (1 2 3 ...)
        f.write("\t".join(str(i) for i in range(1, count + 1)) + "\n")
