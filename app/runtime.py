"""Shared runtime helpers for the Qt frontends."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping

from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtWidgets import QApplication, QFileDialog

from app.audio.engine_legacy import SoundEngine
from app.paths import resource_path
from app.theme.qss import build_qss


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _config_int(config: Mapping[str, object] | None, key: str) -> int | None:
    if config is None:
        return None
    raw = config.get(key)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def configure_qt_runtime() -> None:
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


def build_application() -> QApplication:
    configure_qt_runtime()
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setStyleSheet(build_qss())
    return app


def resolve_soundfont(
    config: Mapping[str, object] | None = None,
    *,
    allow_prompt: bool,
) -> Path:
    env_sf2 = os.environ.get("TIMBAL_SF2_PATH")
    if env_sf2:
        env_candidate = Path(env_sf2)
        if env_candidate.exists():
            return env_candidate

    if config is not None:
        candidate_value = config.get("last_sf2")
        if isinstance(candidate_value, str):
            candidate = Path(candidate_value)
            if candidate.exists():
                return candidate

    bundled = resource_path("soundonts", "timpani_collections.sf2")
    if bundled.exists():
        return bundled

    if not allow_prompt:
        raise FileNotFoundError(
            "No se encontró un SoundFont inicial y el modo actual no abre diálogo."
        )

    chosen, _ = QFileDialog.getOpenFileName(
        None,
        "Seleccionar SoundFont",
        ".",
        "SoundFont (*.sf2)",
    )
    if not chosen:
        raise FileNotFoundError("No seleccionaste ningun SoundFont.")
    return Path(chosen)


def build_audio_engine(
    config: Mapping[str, object] | None = None,
    *,
    allow_prompt: bool,
) -> tuple[SoundEngine, Path]:
    sf2_path = resolve_soundfont(config, allow_prompt=allow_prompt)
    engine = SoundEngine(sf2_path)

    bank = _env_int("TIMBAL_SF2_BANK")
    if bank is None:
        bank = _config_int(config, "sf2_bank")
    if bank is None:
        bank = 0

    preset = _env_int("TIMBAL_SF2_PRESET")
    if preset is None:
        preset = _config_int(config, "sf2_preset")
    if preset is None:
        preset = 0

    try:
        engine.load_sf2_live(sf2_path, bank=bank, preset=preset)
    except Exception as exc:
        print(
            f"WARN: no se pudo aplicar bank/preset al iniciar el engine "
            f"(bank={bank}, preset={preset}): {exc}"
        )

    return engine, sf2_path
