def load_stylesheet():
    # Returns the global stylesheet for the application.
    return """
    /* ---------- Global ---------- */
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
    
    /* ---------- Header / Connection bar ---------- */
    #ConnectionBar {
        background-color: #181c23;
        border-bottom: 1px solid #252a33;
    }

    #ConnectionBar QLabel {
        color: #cfd3da;
        font-size: 12px;
    }

    QComboBox {
        background-color: #1f242d;
        border: 1px solid #303641;
        padding: 3px 6px;
        border-radius: 4px;
        color: #e0e0e0;
    }
    QComboBox::drop-down {
        border: none;
    }

    QLineEdit {
        background-color: #1f242d;
        border: 1px solid #303641;
        border-radius: 4px;
        padding: 3px 6px;
        color: #e0e0e0;
        selection-background-color: #2196f3;
    }

    QPushButton {
        background-color: #252a33;
        border-radius: 4px;
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
        font-size: 12px;
        color: #cfd3da;
    }

    /* ---------- Card group boxes (sidebars) ---------- */
    QGroupBox#CardGroupBox {
        background-color: #111418;
        border: 1px solid #374151;
        border-radius: 8px;
        margin-top: 10px;
    }
    QGroupBox#CardGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        top: 2px;
        padding: 0 2px;
        color: #cfd3da;
        font-weight: 500;
        background-color: #111418;
    }

    #LegendO2HbLabel {
        color: #64b5f6; /* blue */
    }
    #LegendHHbLabel {
        color: #ef5350; /* red */
    }
    #LegendYAxisLabel {
        color: #b0b3ba;
        font-size: 11px;
    }
    #RateValueLabel {
        font-weight: 500;
    }

    /* ---------- Alert sidebar & state badge ---------- */
    QWidget#AlertSidebar {
        background-color: #111418;
    }

    QPushButton#StateBadge {
        border-radius: 12px;
        padding: 6px 16px;
        font-weight: 600;
    }
    QPushButton#StateBadge[state="nominal"] {
        background-color: #2e7d32;
        border: 1px solid #43a047;
        color: white;
    }
    QPushButton#StateBadge[state="alert"] {
        background-color: #c62828;
        border: 1px solid #ef5350;
        color: white;
    }

    /* ---------- Plot widget & cards ---------- */
    QWidget#PlotContainer {
        background-color: #111418;
    }

    QFrame[class~="PlotCard"] {
        background-color: #181c23;
        border-radius: 6px;
        border: 1px solid #252a33;
    }

    QLabel[class~="PlotTitle"] {
        color: #cfd3da;
        font-weight: 500;
        padding-left: 6px;
        padding-top: 2px;
        font-size: 12px;
        background-color: transparent;
    }
    """