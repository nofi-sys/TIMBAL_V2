"""Dialog for selecting a musical note with themed styling."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
)

NOTE_NAMES = "C C# D D# E F F# G G# A A# B".split()


def _build_note_list() -> list[str]:
    return [f"{name}{octave}" for octave in range(0, 9) for name in NOTE_NAMES]


class NoteSelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar nota")
        self.setModal(True)
        self.setObjectName("NoteSelectorDialog")

        layout = QVBoxLayout(self)
        title = QLabel("Elegí la nota para el pad")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.list = QListWidget()
        self.list.addItems(_build_note_list())
        self.list.setSelectionMode(self.list.SingleSelection)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())
        self.list.setMinimumWidth(160)
        layout.addWidget(self.list)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setStyleSheet(
            """
            QDialog#NoteSelectorDialog {
                background-color: #111827;
                color: #e5e7eb;
                border-radius: 8px;
            }
            QDialog#NoteSelectorDialog QLabel {
                color: #e5e7eb;
                font-weight: 500;
                margin-bottom: 4px;
            }
            QDialog#NoteSelectorDialog QListWidget {
                background-color: #1f2937;
                color: #e5e7eb;
                border: 1px solid #334155;
                outline: none;
            }
            QDialog#NoteSelectorDialog QListWidget::item {
                padding: 6px 10px;
            }
            QDialog#NoteSelectorDialog QListWidget::item:selected {
                background-color: #3b82f6;
                color: white;
            }
            QDialog#NoteSelectorDialog QPushButton {
                background-color: #3b82f6;
                border-radius: 6px;
                color: white;
                padding: 6px 14px;
            }
            QDialog#NoteSelectorDialog QPushButton:disabled {
                background-color: #334155;
                color: #64748b;
            }
            """
        )

    def set_current_note(self, note: str) -> None:
        row = self.list.findItems(note, Qt.MatchExactly)
        if row:
            index = self.list.row(row[0])
            self.list.setCurrentRow(index)
            self.list.scrollToItem(row[0], self.list.PositionAtCenter)
        else:
            self.list.setCurrentRow(0)

    def note(self) -> str:
        current = self.list.currentItem()
        return current.text() if current else self.list.item(0).text()
