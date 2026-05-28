from PySide6.QtWidgets import QDialog, QTextEdit, QDialogButtonBox, QVBoxLayout, QLabel


def get_recording_notes(parent=None) -> str | None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Recording Notes")

    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Add notes (example: 00:00:10 - calm):"))

    edit = QTextEdit()
    edit.setPlaceholderText("00:00:10 - calm\n00:01:00 - anxious\n...")
    layout.addWidget(edit)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        text = edit.toPlainText().strip()
        return text if text else None

    return None
