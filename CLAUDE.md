# fNIRS Cognitive Monitor - Project Context

## What this is
PySide6 desktop app that connects to an Artinis OctaMon fNIRS device via Lab Streaming Layer (LSL) through OxySoft, converts optical density to hemoglobin concentration changes via the modified Beer-Lambert law (MBLL), plots live, runs threshold-based cognitive-load alerts, and records sessions to disk.

## Stack
- Python 3.14, PySide6, pyqtgraph, numpy, scipy (planned), pylsl
- Windows 11 primary target

## Hard constraints
- **OxySoft version pinned to 3.2.72.** OxySoft 4.x dropped OctaMon support. Anything we do has to consume 3.2.72's LSL output format. Do NOT trust newer Artinis documentation without cross-checking against the real 3.2.72 exports.
- **Device under test:** Artinis OctaMon (2 receivers x 4 channels = 8 physical fNIRS channels, 16 light sources at 850 nm odd / 760 nm even).
- **English only.** Research software, no i18n.
- **Direct push to main.** No feature branches unless explicitly requested.

## Source-of-truth ordering (when something is in doubt)
1. The real OctaMon device + OxySoft 3.2.72 (when available).
2. Real OxySoft exports at `C:/Users/BARBIC/Desktop/Work/fNIRS/oxysoft 3.2.72/`:
   - `1127_2025_Experiment.txt` - full Direct-Channel OD (32 OD + ADC + Event)
   - `1127_2025_ExperimentHALFRAW.txt` - compact OD (16 active OD)
   - `1127_2025_ExperimentNOTRAW.txt` - O2Hb/HHb concentration deltas
   - `1127_2025_Experiment.oxy4` - OxySoft native binary
   Headers carry real DPF, sample rate, wavelength table, optode distances. Use these as ground truth.
3. Artinis public docs - cross-check against 3.2.72 exports, do not trust blindly.
4. This codebase - treat as a hypothesis to verify, not a specification.

## The simulator is NOT a reference
A separate project at `C:/Users/BARBIC/PycharmProjects/fNIRSimulator` emits a fake LSL stream for dev when no device is around. It was written downstream of this monitor and only proves circular consistency. Do not validate the monitor against the simulator. If they disagree, the monitor is more likely correct.

## Current status
Mid-remediation. A full audit and 8-phase remediation plan are in `docs/REMEDIATION_PLAN.md`. Work through the phases in order. Each phase has its own exit criteria.

## Working agreements specific to this project
- DPF, interoptode distance, and extinction coefficients are scientific constants that may change per study. They live in `config/defaults.py` as defaults but are overridable from the Settings dialog (Phase 6).
- These values must NOT be editable while a recording is in progress.
- Every recording folder must be self-describing: `metadata.json` carries the DPF, distance, coefficients, channel layout, sample rate, and app version that were applied to that recording.
- Recording is sacred. It must be lossless. If there's a tradeoff between display smoothness and recording integrity, recording wins every time.
- When proposing changes to MBLL math, signal conditioning, or alert algorithms: verify against the real OxySoft exports before claiming correctness. "It looks plausible on the plot" is not verification.
