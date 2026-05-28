# fNIRS Cognitive Monitor

Real-time desktop monitor for the Artinis OctaMon fNIRS device. Consumes Lab Streaming Layer (LSL) optical-density (OD) output from OxySoft 3.2.72, converts to hemoglobin concentration changes via the modified Beer-Lambert law (MBLL), displays live traces, detects elevated cognitive load through a per-subject calibrated threshold + frontal-asymmetry detector, and records lossless sessions to disk in both OxySoft-style TSV and SNIRF formats.

## Status

Mid-to-late development. All 62 tests pass; the cognitive-load algorithm is the Phase A baseline and has **not yet been validated against a labeled cognitive task**. See `docs/REMEDIATION_PLAN.md` for the full development history and the planned post-Phase-8 validation work.

## Hard constraints

- Windows 11 primary target. Python 3.12+.
- OxySoft version pinned to **3.2.72** (4.x dropped OctaMon support).
- Device: Artinis OctaMon (2 receivers, 8 transmitters, 16 light sources at 850 / 760 nm).
- English-only UI (research software).

## Quickstart

```powershell
git clone https://github.com/BarBichachi/fNIRSMonitor.git
cd fNIRSMonitor
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

On first launch you'll be prompted to choose a recordings folder (default: `Documents/fNIRS Monitor/Recordings`). Cancel to keep the default. Change later via the **Settings** button in the top bar.

## Connecting to a device

1. Start OxySoft 3.2.72 and begin a measurement so it pushes a Direct-Channel OD LSL stream.
2. In the monitor: **Refresh** -> pick the stream -> **Connect**.
3. Click **Calibrate Subject (60s)** in the right sidebar with the subject sitting quietly. Alerts only fire after calibration.

If you don't have a device, the companion project `fNIRSimulator` (separate repo) emits a fake LSL stream for development. Note: the simulator was written to match this monitor's expectations, so agreement between them proves nothing about real-device correctness.

## What you get per recording

Each recording produces an isolated folder under your recordings root:

```
<root>/<DD-MM-YYYY>/<HH-MM-SS_session_NN>/
    raw_od.tsv         OxySoft-style raw OD export (32 channels + ADC + Event)
    calculated.tsv     post-MBLL O2Hb + HHb deltas per channel (unfiltered)
    metadata.json      DPF, interoptode distance, coefficients, sample rate,
                       stream identity, app version, channel layout
    session.snirf      same Hb time series in SNIRF v1.1 format for
                       MNE-NIRS / Homer3 / NIRS-KIT
    notes.txt          operator notes (only if you typed any when stopping)
```

The recordings are atomically self-describing. You can zip the folder and hand it to an analyst without losing context.

**Filter behavior:** the live plot and the load detector see a 0.01-0.5 Hz causal Butterworth bandpass. The TSV and SNIRF files store **unfiltered** post-MBLL values so you can apply any offline pipeline you want.

## Settings

Edit via the **Settings** button or by hand-editing `%LOCALAPPDATA%/fNIRS Monitor/settings.json`. Validated on load; bad values fall back to defaults.

Tabs:

- **General** - recordings folder, reconnect tolerance (default 5 s), nominal-sound suppress window (default 5 s).
- **Acquisition** - DPF (default 6.56), interoptode distance (default 3.5 cm). **Locked while recording.** Read-only wavelength order + extinction coefficients shown for reference.
- **Calibration** - baseline mode (`single_sample` matches OxySoft, `window` averages N seconds), baseline window length, per-subject load-detector calibration length.
- **Alerting** - k_sd (default 1.5), active window (default 30 s), min elevated channels (default 2), HHb sanity tolerance (default 0.5 uM).

Settings changes take effect immediately via `controller.reload_settings()`. Recording-root changes apply to the next recording.

## Tests

```powershell
pytest tests/ -v
```

62 tests covering MBLL math replay against real OxySoft NOTRAW exports, LSL metadata contract, Butterworth filter behavior, baseline modes, cognitive-load detector calibration + decisions, signal quality (std + CV + heartbeat), SNIRF writer + integration.

The MBLL replay test reads real OxySoft files from `%FNIRS_REFERENCE_DATA%` if set, otherwise from `C:\Users\BARBIC\Desktop\Work\fNIRS\oxysoft 3.2.72`. Skipped cleanly when those files aren't present.

## Logs

Rotating log files live at `%LOCALAPPDATA%/fNIRS Monitor/logs/fnirs_monitor.log` (2 MB per file, 5 backups). Errors and warnings also go to stderr.

## Architecture (one-paragraph)

`logic/lsl_client` owns the LSL inlet and pulls chunks on a dedicated QThread; it validates stream metadata before announcing a connection. `logic/data_processor` wires together MBLL math, a causal Butterworth filter, baseline-mode bookkeeping, signal-quality evaluation, and a pluggable `LoadDetector`. `utils/session_recorder` buffers samples in memory and on disk; it owns a background `RecordingWriter` thread for lossless TSV emission and writes SNIRF + metadata.json at session stop. `logic/app_controller` is the orchestrator that wires LSL chunks to processing to recording to UI, manages pause/resume across short disconnects, threads timestamps through, and exposes a settings reload path. The UI in `views/` is pure Qt/PySide6 with `pyqtgraph` for plots; widgets observe controller signals and poll the detector for calibration progress.

## Repo layout

```
config/           defaults, user-settings overlay, schema validation
logic/            LSL transport, data processing, load detection, filters
utils/            session recorder, recording writer (bg thread), SNIRF writer,
                  enums, sound, paths, logging
views/            main window, widgets, settings dialog
tests/            pytest suite
scripts/          diagnostics + headless smoke tests
docs/             remediation plan (development history)
```

## Acknowledgements

MBLL extinction coefficients: Matcher et al. 1995 (matches MNE-NIRS / Homer3 / NIRS-KIT). Channel mapping convention: OctaMon 2x4 (active light sources L1-L8 on Rx1, L9-L16 on Rx2; odd index = 850 nm, even = 760 nm).
