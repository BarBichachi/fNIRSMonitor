from enum import Enum


class CognitiveState(Enum):
    NOMINAL = "Nominal"
    LOAD = "Cognitive Load"
    # Window-baseline mode is still accumulating its baseline buffer; no
    # delta values are available yet, alerts are suppressed.
    WARMING_UP = "Warming Up"
    # Per-subject load-detector baseline is being established (Phase 4).
    CALIBRATING = "Calibrating"