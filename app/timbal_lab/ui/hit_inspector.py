"""Inspector widget for analyzed timbal lab sessions."""
from __future__ import annotations

import json
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class HitInspector(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, object]] = []
        self._report: dict[str, object] = {}
        self._build_ui()

    def clear(self) -> None:
        self._rows = []
        self._report = {}
        self.summary_label.setText("Sin analisis cargado.")
        self.table.setRowCount(0)
        self.details.setPlainText("")

    def load_analysis(self, session_dir: Path, analysis_dir: Path) -> None:
        report_path = analysis_dir / "benchmark_report.json"
        rows_path = analysis_dir / "hits_analysis.jsonl"
        calibration_path = analysis_dir / "calibration_summary.json"

        self._report = _read_json(report_path) if report_path.exists() else {}
        calibration = _read_json(calibration_path) if calibration_path.exists() else {}
        self._rows = _read_jsonl(rows_path) if rows_path.exists() else []

        winner = self._report.get("winner", "unknown")
        thresholds = calibration.get("thresholds", {})
        temporal = calibration.get("temporal", {})
        self.summary_label.setText(
            " | ".join(
                [
                    f"Sesion: {session_dir.name}",
                    f"Winner: {winner}",
                    f"Hits: {len(self._rows)}",
                    f"thr={thresholds.get('hit_threshold', '--')}",
                    f"delta={thresholds.get('delta_threshold', '--')}",
                    f"refr={thresholds.get('refractory_ms', '--')}ms",
                    f"tauE={temporal.get('tau_energy_ms', '--')}ms",
                ]
            )
        )

        columns = [
            ("hit_id", "Hit"),
            ("channel", "Ch"),
            ("intensity_input_norm", "Int"),
            ("peak_value", "Peak"),
            ("initial_slope", "Slope"),
            ("pre_hit_energy", "PreE"),
            ("legacy_velocity_main", "LegacyVel"),
            ("legacy_brightness_0_1", "LegacyBri"),
            ("state_velocity_main", "StateVel"),
            ("state_brightness_0_1", "StateBri"),
            ("state_decay_ms", "StateDecay"),
            ("state_contact_state", "Contact"),
            ("state_repeat_state", "Repeat"),
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels([label for _, label in columns])
        self.table.setRowCount(len(self._rows))

        for row_index, row in enumerate(self._rows):
            for col_index, (field, _) in enumerate(columns):
                value = row.get(field)
                item = QTableWidgetItem(_fmt(value))
                if isinstance(value, (int, float)):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, col_index, item)

        self.table.resizeColumnsToContents()
        if self._rows:
            self.table.selectRow(0)
            self._update_details(0)
        else:
            self.details.setPlainText("No hay filas analizadas todavia.")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.summary_label = QLabel("Sin analisis cargado.")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        splitter = QSplitter(Qt.Vertical, self)
        root.addWidget(splitter, 1)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.table)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        splitter.addWidget(self.details)
        splitter.setSizes([360, 220])

    def _on_selection_changed(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            self.details.setPlainText("")
            return
        self._update_details(indexes[0].row())

    def _update_details(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self._rows):
            self.details.setPlainText("")
            return
        row = self._rows[row_index]
        detail = {
            "selected_hit": row,
            "benchmark_summary": self._report,
        }
        self.details.setPlainText(json.dumps(detail, ensure_ascii=True, indent=2))


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _fmt(value: object) -> str:
    if value is None:
        return "--"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)
