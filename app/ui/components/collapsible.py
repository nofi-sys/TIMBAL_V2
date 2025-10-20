"""Simple collapsible panel widget used in the UI."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QToolButton, QVBoxLayout, QWidget


class CollapsiblePanel(QFrame):
    def __init__(self, title: str, content: QWidget, *, collapsed: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CollapsiblePanel")
        self._content = content
        self._collapsed = collapsed
        self._toggle_callbacks: list[callable[[bool], None]] = []

        self._header = QToolButton(text=title)
        self._header.setObjectName("CollapsibleHeader")
        self._header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._header.setArrowType(Qt.RightArrow if collapsed else Qt.DownArrow)
        self._header.setCheckable(True)
        self._header.setChecked(not collapsed)
        self._header.clicked.connect(self.toggle)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._content)

        self._apply_state()

    def on_toggled(self, callback: callable[[bool], None]) -> None:
        self._toggle_callbacks.append(callback)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self._header.setArrowType(Qt.RightArrow if collapsed else Qt.DownArrow)
        self._header.setChecked(not collapsed)
        self._apply_state()
        for callback in self._toggle_callbacks:
            callback(self._collapsed)

    def toggle(self) -> None:
        self.set_collapsed(not self._collapsed)

    def _apply_state(self) -> None:
        self._content.setVisible(not self._collapsed)

