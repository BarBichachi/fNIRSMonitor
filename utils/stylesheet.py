def load_stylesheet():
    # Returns the global stylesheet for the application.
    return """
    /* ---------- Global ---------- */
    QWidget#MainBackground {
    background-color: #262b35;
    }
    
    QMainWindow {
        background-color: #111418;
        color: #e0e0e0;
        font-family: "Segoe UI", "Roboto", sans-serif;
        font-size: 13px;
    }

    QLabel {
        background-color: transparent;
        color: #e0e0e0;
    }
    
    QGroupBox {
        font-size: 14px;
        font-weight: 600;
    }
    
    /* ---------- Header / Connection bar ---------- */
    QWidget#ConnectionBar {
        background-color: #2b303a;
        border-bottom: 1px solid #303846;
        padding: 6px 10px;
    }

    QWidget#ConnectionBar QLabel {
        color: #dde2ea;
        font-size: 13px;
    }

    QComboBox {
        background-color: #1f242d;
        border: 1px solid #303641;
        padding: 3px 6px;
        border-radius: 6px;
        color: #e0e0e0;
    }
    QComboBox::drop-down {
        border: none;
    }

    QLineEdit {
        background-color: #1f242d;
        border: 1px solid #303641;
        border-radius: 6px;
        padding: 3px 6px;
        color: #e0e0e0;
        selection-background-color: #2196f3;
    }

    QPushButton {
        background-color: #252a33;
        border-radius: 6px;
        border: 1px solid #303641;
        padding: 4px 10px;
        color: #e0e0e0;
    }
    QPushButton:hover {
        background-color: #2c323d;
    }
    QPushButton:pressed {
        background-color: #20242c;
    }

    QPushButton#PrimaryButton {
        background-color: #2196f3;
        border-color: #2196f3;
        color: white;
        font-weight: 500;
    }
    QPushButton#PrimaryButton:hover {
        background-color: #42a5f5;
    }
    QPushButton#PrimaryButton:pressed {
        background-color: #1e88e5;
    }

    QPushButton#RecordButton {
        background-color: #d32f2f;
        border-color: #d32f2f;
        color: white;
        font-weight: 600;
    }
    QPushButton#RecordButton:checked {
        background-color: #b71c1c;
        border-color: #b71c1c;
    }

    QLabel#TimerLabel {
        font-family: "Consolas", monospace;
        font-size: 14px;
        color: #dde2ea;
    }

    /* ---------- Card group boxes (sidebars) ---------- */
    QGroupBox#CardGroupBox {
        background-color: #111418;
        border: 1px solid #3c4655;
        border-radius: 10px;
        margin-top: 10px;
    }
    QGroupBox#CardGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        top: 2px;
        padding: 0 4px;
        color: #dde2ea;
        font-weight: 600;
        font-size: 14px;
    }

    #LegendO2HbLabel {
        color: #ef5350; /* red */
    }
    #LegendHHbLabel {
        color: #64b5f6; /* blue */
    }
    #LegendYAxisLabel {
        color: #bcc1cc;
        font-size: 12px;
    }
    #RateValueLabel {
        font-weight: 600;
    }

    /* ---------- Signal state dots ---------- */
    QLabel#SignalDot {
        min-width: 10px;
        min-height: 10px;
        max-width: 10px;
        max-height: 10px;
        border-radius: 5px;
        background-color: #d32f2f;  /* default red */
    }
    
    /* Dynamic state-based colors */
    QLabel#SignalDot[state="green"] {
        background-color: #4caf50;
    }
    
    QLabel#SignalDot[state="red"] {
        background-color: #d32f2f;
    }
    
    /* ---------- Alert group box ---------- */
    QGroupBox#AlertSideBar {
        background-color: #111418;
        border: 1px solid #3c4655;
        border-radius: 10px;
        margin-top: 10px;
        padding: 8px;
    }
    QGroupBox#AlertSideBar::title {
        subcontrol-origin: margin;
        left: 10px;
        top: 2px;
        padding: 0 4px;
        color: #dde2ea;
        font-weight: 600;
        font-size: 16px;
    }
    
    QGroupBox#AlertSideBar QLabel {
        font-size: 14px;     
        color: #e2e6ee;
    }
    
    QGroupBox#AlertSideBar QDoubleSpinBox,
    QGroupBox#AlertSideBar QSpinBox {
        min-height: 28px;
        font-size: 14px;
    }

    /* ---------- State badge ---------- */
    QLabel#StateBadge {
    border-radius: 16px;
    padding: 18px 10px;
    font-weight: 600;
    font-size: 24px;
    letter-spacing: 1px;
    text-transform: uppercase;
    }

    /* Nominal state */
    QLabel#StateBadge[state="nominal"] {
    background-color: #43a047;
    border: 1px solid #a5d6a7;
    color: #ffffff;
    }

    /* Alert state */
    QLabel#StateBadge[state="alert"] {
    background-color: #e53935;
    border: 1px solid #ff8a80;
    color: #ffffff;
    }

    /* ---------- Plot widget & cards ---------- */
    QWidget#PlotContainer {
        background-color: #111418;
    }

    QFrame[class~="PlotCard"] {
        background-color: #181c23;
        border-radius: 10px;
        border: 1px solid #303846;
    }

    QLabel[class~="PlotTitle"] {
        color: #e3e7ef;
        font-weight: 600;
        padding-left: 6px;
        padding-top: 2px;
        font-size: 14px;
        background-color: transparent;
    }
    
    /* ---------- Calibration dialog ---------- */
    QDialog#CalibrationDialog {
        background-color: #181c23;
    }
    
    QDialog#CalibrationDialog QLabel {
        color: #e0e3ea;
    }
    
    /* Stop button in calibration dialog */
    QPushButton#CalibrationStopButton {
        background-color: #252a33;
        border-radius: 6px;
        border: 1px solid #303641;
        padding: 6px 10px;
        color: #e0e0e0;
    }
    QPushButton#CalibrationStopButton:hover {
        background-color: #2c323d;
    }
    QPushButton#CalibrationStopButton:pressed {
        background-color: #20242c;
    }
    """