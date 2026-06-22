# fNIRS Monitor - Phased Remediation Plan

Approved 2026-05-28. Audit findings and design rationale in conversation history.

**Commit strategy:** one commit per phase by default, push to main after exit criteria pass. No feature branches.

---

## Phase 0 - Foundation: settings layer + folder layout

**Why first:** later phases all touch DPF / interoptode / recording paths. Need one stable settings API before scattering reads/writes.

**Files:**
- New: `config/__init__.py`, `config/defaults.py`, `config/user_settings.py`, `config/schema.py`
- Delete: old `config.py` (re-exports preserved via `config/__init__.py`)
- New: `utils/app_paths.py` (resolves recordings root, asset paths, settings.json location)
- Touch: every file that does `import config` (import path only, no logic change)

**Behavior:**
- Code defaults in `config/defaults.py` (DPF=6.56, distance=3.5, coefficients, asset paths, window sizes).
- User overrides loaded from `%LOCALAPPDATA%/fNIRS Monitor/settings.json` at startup.
- `config.DPF` etc. read from merged view (override or default).
- First run: file doesn't exist, defaults used, file created on first save.
- `config.SAMPLE_RATE` removed as a *mutable* module global. DataProcessor tracks its own rate as instance state.
- Asset paths resolved through `app_paths.resource("assets/...")`.

**Exit criteria:**
- App launches identically to today with no settings.json.
- Edit DPF in settings.json by hand, restart, header shows new value.
- No remaining writes to `config.X` anywhere.

---

## Phase 1 - Recording integrity

**Why next:** without this, every subsequent test on real data is suspect.

**Files:**
- `logic/lsl_client.py`, `logic/app_controller.py`, `utils/session_recorder.py`
- New: `utils/recording_writer.py` (background-thread writer with bounded queue)

**Changes:**
1. **LSL pull rewrite (C1):** replace `QTimer + pull_sample(timeout=0.0)` with a dedicated worker loop calling `inlet.pull_chunk(max_samples=64, timeout=0.05)`. Every sample emitted, none dropped. Display throttled separately at 60 Hz.
2. **Atomic per-sample write (C2):** one method `recorder.write(...)` writes both files OR a sentinel row to both. Sample index advances once per LSL sample.
3. **Background-thread writer (C5):** runs on its own thread, consumes a `queue.Queue`, buffered writes, flush every 1s and on `stop()`. Bounded queue (~10000 rows) with overflow logged as event marker.
4. **Pause/resume across short disconnects (C6):** `recorder.pause()` / `recorder.resume()`. On disconnect, pause + start tolerance timer (default 5s). If reconnect within tolerance AND same source_id, resume + write `EVENT: stream-resumed-after-Xms`. Else stop.
5. **NaN guard (I6):** if `np.isfinite(od_vec).all()` is false, write sentinel row, skip processing.
6. **Idempotent disconnect + StreamInlet try/except (I9).**
7. **Per-recording folder layout:**
   ```
   <recordings_root>/<dd-mm-yyyy>/<HH-MM-SS_session_name_NN>/
       raw_od.tsv
       calculated.tsv
       metadata.json
       notes.txt (if any)
   ```
   `metadata.json` at `start()` carries sample_rate, DPF, distance, coefficients, channel layout, stream source_id, app version, start_time_iso. SNIRF added Phase 7.

**Exit criteria:**
- Record 60s @ 50 Hz from simulator: row count ~3000 +/- a few.
- Unplug + replug within 5s: same recording continues with event marker.
- `cut -f1 raw_od.tsv` matches `cut -f1 calculated.tsv` sample-by-sample.

---

## Phase 2 - LSL contract + math validation

**Why next:** lossless recording of garbage is still garbage.

**Files:**
- `logic/lsl_client.py`, `logic/data_processor.py`
- New: `tests/test_mbll_against_oxysoft.py`, `tests/fixtures/` (small slice of real exports)

**Changes:**
1. **Stream metadata contract (C3):** on connect, walk `inlet.info().desc()` to extract per-channel Rx, L (light source index), wavelength. Reject connection (loud error, no "connected" UI state) if channel count not in {32, 33, 34}, wavelengths not {760, 850}, or labels unparseable.
2. **Dynamic channel-map build:** build `od_indices` by pairing each receiver's light sources by wavelength, not by hardcoded position.
3. **Replay test:** parse `1127_2025_Experiment.txt`, run pipeline with DPF=6.56, distance=3.5, current coefficients. Compare against `1127_2025_ExperimentNOTRAW.txt`. Pass: per-sample RMSE < 0.05 uM, max abs error < 0.5 uM across all 16 traces over first 60s.
4. **If test fails:** swap to Cope & Delpy 1988 values, re-run. If still fails, investigate scale/unit. Either way document source in `defaults.py`.
5. **Scale-unit comment block** in `data_processor.py` explaining OD = log10(2^16 / I_raw), MBLL consumes deltaOD, output uM.

**Exit criteria:**
- Replay test passes.
- `python -m pytest` clean.
- Bad metadata refuses to connect with clear error.

---

## Phase 3 - Signal conditioning

**Why:** required for Phase 4 to produce anything trustworthy.

**Files:**
- New: `logic/signal_filter.py` (per-channel causal Butterworth state)
- `logic/data_processor.py`

**Changes:**
1. Causal Butterworth bandpass 0.01-0.5 Hz per channel via `scipy.signal.sosfilt_zi` + `sosfilt`. Per-channel state persisted. (Add `scipy` to requirements.)
2. Filter coefficients recomputed when stream rate is detected. If rate too low for 0.5 Hz lowpass, downgrade to `0.4 * Nyquist` and log warning.
3. **Baseline modes:**
   - Mode A `single_sample_baseline` (default): current behavior.
   - Mode B `window_baseline`: buffer N seconds, baseline = mean, emit deltas from sample N+1.
   - Mode C manual: "Set Baseline Now" button recomputes baseline as mean of last N seconds.
   Modes A/B mutually exclusive; manual button always available.
4. **WARMING_UP state:** while in Mode B before baseline completes, dim plots, hide alert.

**Exit criteria:**
- Pure DC offset in OD goes to zero in deltaHb (highpass works).
- Simulated 1 Hz oscillation attenuated (lowpass works).
- Mode B with 10s window: no calculated rows for first 10s.
- "Set Baseline" button re-zeros plot immediately.

---

## Phase 4 - Cognitive-load detection (Phase A algorithm)

**Files:**
- New: `logic/load_detector.py` (pluggable interface)
- `logic/data_processor.py` (delegates)
- `views/widgets/alert_sidebar.py`
- `utils/enums.py` (add `CALIBRATING`, `WARMING_UP`)

**Algorithm (Phase A):**

```
Post-filter inputs: O2Hb[8], HHb[8], quality[8]
Windows: rest_window_s=60 (per-subject baseline), active_window_s=30 (current state)

Session start: "Establish Per-Subject Baseline" button (subject quiet 60s).
  Compute baseline_mean[8], baseline_std[8] for filtered O2Hb.
  Compute baseline asymmetry mean+std.

Each sample, over last 30s of filtered data:
  curr_mean[8]  = mean O2Hb per channel
  curr_HHb[8]   = mean HHb per channel
  good_channels = (quality == 'green')

  per_channel_elevated[i] =
    (curr_mean[i] > baseline_mean[i] + k_sd * baseline_std[i])
    AND (curr_HHb[i] <= baseline_HHb_mean[i] + small_tol)   # HHb sanity gate
    AND good_channels[i]

  asymmetry = mean(curr_mean[R]) - mean(curr_mean[L])
  elevated_asymmetry = asymmetry > (baseline_asymmetry_mean + k_sd * baseline_asymmetry_sd)

  LOAD when (sum(per_channel_elevated[R]) >= 2) OR elevated_asymmetry
  NOMINAL otherwise.

k_sd default 1.5, exposed as setting.
```

**UI:**
- Alert sidebar gets "Calibrate Subject (60s)" button + progress + readout of `baseline_mean +/- SD`.
- Today's IF/FOR spinboxes become advanced controls (`k_sd`, active_window_s, min_elevated_channels) under a "Tuning" disclosure.
- New `CognitiveState.CALIBRATING` badge color, alert sounds disabled during calibration.

**Pluggable interface:**
- `class LoadDetector: update(o2hb, hhb, quality) -> CognitiveState`. Default `ThresholdAsymmetryDetector`. Swappable when labeled data arrives.

**Exit criteria:**
- Synthetic: sustained "right-PFC O2Hb up, HHb flat" 20s -> LOAD. Returns to NOMINAL after.
- Synthetic: "O2Hb up AND HHb up" (motion) -> stays NOMINAL.
- Calibration required before alerts can fire.

**Not in scope here:** validation against real cognitive task data. Separate labeled-data session later.

---

## Phase 5 - Real signal quality

**Files:**
- `logic/data_processor.py`, `views/widgets/control_sidebar.py`

**Per channel each sample, over last 5s of raw OD:**
- `std(OD) > QUALITY_STD_LOWER` (default 0.005, exposed).
- `coefficient_of_variation < threshold` (no flat-lining or runaway).
- Heartbeat presence: FFT peak in 0.8-2.0 Hz exceeds noise floor by 3x, recomputed every 1s.
- All three good -> green. Two -> yellow. Less -> red.

**Exit criteria:**
- All-zero OD -> red.
- Simulated breathing (0.3 Hz) + heartbeat (1.2 Hz) -> green.
- Disconnect one optode in simulation -> that channel red within 5s.

---

## Phase 6 - UI / UX

**Files:**
- `views/widgets/connection_bar.py`, `views/widgets/control_sidebar.py`, `views/main_window.py`
- New: `views/dialogs/settings_dialog.py`, `views/widgets/calibration_panel.py`
- `utils/sound_player.py`

**Changes:**
1. **First-run folder picker:** on first launch, modal "Choose where to save recordings", default `Documents/fNIRS Monitor/Recordings`. Stored in settings.
2. **Settings dialog (gear icon in connection bar):**
   - General: recordings folder, reconnect tolerance.
   - Acquisition: DPF, interoptode distance (cm), wavelength order display (read-only, from stream).
   - Calibration: baseline mode A/B, baseline window, calibration window.
   - Alerting: k_sd, active window, min elevated channels.
3. **DPF/distance UI:** persistent readout in left sidebar. "Edit" link opens Settings -> Acquisition.
4. **Block DPF/distance during recording:** Settings -> Acquisition page read-only when `recorder.is_recording`. Tooltip explains why.
5. **Connect button loading state:** disable + spinner during in-flight `find_streams` / `connect_to_stream`. Re-enable on signal or 10s timeout.
6. **Sound debouncing:** after `nominal` plays, suppress further `nominal` plays for 5s.
7. **Asset path resolution:** via `app_paths.resource()`.
8. **Auto-reconnect during pause window:** try `find_streams` for same source_id once per second through the tolerance window.

**Exit criteria:**
- First launch with no settings prompts for folder.
- Settings round-trip: open, edit DPF, save, restart, value persists.
- Recording active -> Settings Acquisition fields disabled.
- Connect button spins, no re-click during in-flight.
- Rapid alert/nominal oscillation no longer spams "nominal" sound.

---

## Phase 7 - SNIRF export + metadata.json

**Files:**
- New: `utils/snirf_writer.py`
- `utils/recording_writer.py`
- `requirements.txt`: add `pysnirf2`

**Changes:**
- `metadata.json` already added in Phase 1.
- SNIRF written at `stop()` from in-memory buffer (60-min @ 50 Hz = ~180k samples, fits in RAM).
- Channel layout, wavelengths, OctaMon optode positions, DPF, distance written to SNIRF metadata per spec.

**Exit criteria:**
- `session.snirf` opens in MNE-NIRS (`mne.io.read_raw_snirf`) without errors.
- MNE-NIRS HbO plot matches our `calculated.tsv` values.

---

## Phase 8 - Polish + cleanup

- Remove dead code: `raw_buffer`, `PLACEHOLDER_LO`, `PAIR_VARIANCE_THRESH`, unused `WINDOW_HEIGHT`.
- Replace remaining O(N) shifts with ring buffers if any consumers survive.
- `logging` module: rotating file in app data dir + console. Replace all `print()`.
- `sys.excepthook` -> log + Qt error dialog + exit cleanly.
- `requirements.txt` with pinned versions.
- Project runnable as `python -m fnirs_monitor` from any CWD.
- README.md with quickstart and "what files you get per recording".
- Unit tests for: MBLL math (Phase 2), filter (Phase 3), load detector synthetics (Phase 4), signal quality (Phase 5), session-naming utilities.

**Exit criteria:**
- `python -m pytest` passes.
- `python main.py` from any CWD works.
- One session produces clean folder: raw_od.tsv, calculated.tsv, session.snirf, metadata.json, optional notes.txt.

---

## After Phase 8: labeled-data follow-up

Separate session, not blocking this work:
- Design controlled task (N-back recommended: 0-back / 2-back / 3-back blocks with rest).
- Record 5-10 subjects.
- Replay through alternative load detectors offline via `LoadDetector` interface.
- Pick best, set as default. Document choice.

## Outstanding reminders for Bar
- ~~After Phase 2 ships: confirm whether coefficients matched OxySoft's NOTRAW (if test passed) or were swapped to Cope & Delpy (if not). Either way document.~~ **Resolved (Phase 2).** Replay test initially showed ~2.5x scale error with the previous set; diagnostic (`scripts/diagnose_mbll_replay.py`) compared Cope / Matcher / Wray and **Matcher et al. 1995** won. Replay now passes (RMSE 0.048 uM, max abs error 0.197 uM). Residual ~10% uniform scale gap vs OxySoft NOTRAW is expected (OxySoft's internal coefficient table is not public) and irrelevant for relative deltaHb dynamics. Documented in `config/defaults.py`.
- After Phase 8: design and run the labeled cognitive task data collection.

---

## Dependencies and parallelism

Strictly sequential: 0 -> 1 -> 2. Independent (could parallelize): 3, 4, 5. Phase 6 depends on 0 + ideally 3/4/5. Phase 7 depends on 1 + 2.

Cadence: 0+1 together, 2 alone, 3-5 together, 6 alone, 7 alone, 8 alone. Roughly 5-6 working sessions total.
