"""Shared visual shell for the testing apps."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class MetricCard(QFrame):
    def __init__(self, title: str, parent=None, *, value_size: int = 24) -> None:
        super().__init__(parent)
        self.setObjectName("TestingMetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("TestingMetricTitle")
        self.value_label = QLabel("--")
        self.value_label.setObjectName("TestingMetricValue")
        self.value_label.setProperty("valueSize", value_size)
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class SectionCard(QFrame):
    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TestingSectionCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("TestingSectionTitle")
        layout.addWidget(self.title_label)

        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("TestingSectionSubtitle")
            self.subtitle_label.setWordWrap(True)
            layout.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None

        self.body = QWidget(self)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(10)
        layout.addWidget(self.body)


class StatusChip(QLabel):
    def __init__(self, text: str = "Pendiente", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("TestingStatusChip")
        self.setAlignment(Qt.AlignCenter)
        self.set_status(text, tone="neutral")

    def set_status(self, text: str, *, tone: str = "neutral") -> None:
        self.setText(text)
        self.setProperty("tone", tone)
        style = self.style()
        style.unpolish(self)
        style.polish(self)


def build_testing_qss(extra: str = "") -> str:
    return (
        """
        QLabel#TestingHeadline {
            color: #f8fafc;
            font-size: 30px;
            font-weight: 700;
        }
        QLabel#TestingSubheadline {
            color: #94a3b8;
            font-size: 14px;
        }
        QLabel#TestingHint {
            color: #94a3b8;
            font-size: 13px;
        }
        QFrame#TestingMetricCard {
            background: #0f172a;
            border: 1px solid #243244;
            border-radius: 18px;
        }
        QLabel#TestingMetricTitle {
            color: #94a3b8;
            font-size: 12px;
            font-weight: 600;
        }
        QLabel#TestingMetricValue {
            color: #e5e7eb;
            font-size: 24px;
            font-weight: 700;
        }
        QLabel#TestingMetricValue[valueSize="20"] {
            font-size: 20px;
        }
        QLabel#TestingMetricValue[valueSize="18"] {
            font-size: 18px;
        }
        QFrame#TestingSectionCard {
            background: #111827;
            border: 1px solid #243244;
            border-radius: 22px;
        }
        QLabel#TestingSectionTitle {
            color: #f8fafc;
            font-size: 16px;
            font-weight: 700;
        }
        QLabel#TestingSectionSubtitle {
            color: #94a3b8;
            font-size: 13px;
        }
        QLabel#TestingStatusChip {
            border-radius: 12px;
            padding: 6px 12px;
            font-size: 12px;
            font-weight: 700;
        }
        QLabel#TestingStatusChip[tone="neutral"] {
            background: #1e293b;
            color: #cbd5e1;
            border: 1px solid #334155;
        }
        QLabel#TestingStatusChip[tone="ok"] {
            background: #0f2f1f;
            color: #86efac;
            border: 1px solid #166534;
        }
        QLabel#TestingStatusChip[tone="warn"] {
            background: #3b220f;
            color: #fcd34d;
            border: 1px solid #b45309;
        }
        QLabel#TestingStatusChip[tone="danger"] {
            background: #3b1111;
            color: #fca5a5;
            border: 1px solid #b91c1c;
        }
        QLabel#TestingStatusChip[tone="info"] {
            background: #10243e;
            color: #93c5fd;
            border: 1px solid #2563eb;
        }
        QPushButton#SecondaryAction {
            background: #1e293b;
            color: #e5e7eb;
            border: 1px solid #334155;
        }
        QPushButton#DangerAction {
            background: #7f1d1d;
            color: #fee2e2;
            border: 1px solid #b91c1c;
        }
        QComboBox,
        QSpinBox,
        QLineEdit,
        QPlainTextEdit,
        QTableWidget {
            background: #020617;
            color: #e5e7eb;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 6px 8px;
        }
        QComboBox::drop-down {
            border: 0;
            width: 24px;
        }
        QTabWidget::pane {
            border: 1px solid #243244;
            border-radius: 16px;
            background: #0b1220;
            top: -1px;
        }
        QTabBar::tab {
            background: #172131;
            color: #94a3b8;
            border: 1px solid #243244;
            border-bottom: 0;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            padding: 8px 12px;
            margin-right: 4px;
        }
        QTabBar::tab:selected {
            background: #0b1220;
            color: #f8fafc;
        }
        QHeaderView::section {
            background: #172131;
            color: #cbd5e1;
            border: 0;
            border-right: 1px solid #243244;
            border-bottom: 1px solid #243244;
            padding: 6px 8px;
        }
        """
        + extra
    )
