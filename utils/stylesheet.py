def load_stylesheet():
    # Returns the global stylesheet for the application.
    return """
        QWidget {
            background-color: #f0f0f0;
            color: #333;
            font-family: Arial;
            font-size: 14px;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #ccc;
            border-radius: 5px;
            margin-top: 0.5em;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
        }
        QPushButton {
            background-color: #e0e0e0;
            border: 1px solid #b0b0b0;
            border-radius: 4px;
            padding: 8px 12px;
        }
        QPushButton:hover {
            background-color: #e9e9e9;
        }
        QPushButton:pressed, QPushButton:checked {
            background-color: #0078d4;
            color: white;
            border-color: #005a9e;
        }
        QPushButton:disabled {
            background-color: #f5f5f5;
            color: #c0c0c0;
        }
        QLineEdit, QComboBox, QSpinBox {
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 5px;
            background-color: white;
        }
        /* --- ADDED: Style for the dark plot placeholder --- */
        #plotPlaceholder {
            background-color: #1a1a1a;
            border-radius: 5px;
        }
    """