#!/usr/bin/env python3
"""Testing variant that mirrors the main UI but keeps its own config."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _settings_module():
    from app.state import settings

    return settings


def _testing_config_path() -> Path:
    settings = _settings_module()
    return settings._app_config_dir() / "config_testeo.json"


def _seed_testing_config(config_path: Path) -> None:
    if config_path.exists():
        return

    original = config_path.with_name("config.json")
    if not original.exists():
        return

    try:
        config_path.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:
        pass


def _original_config() -> dict:
    original = _testing_config_path().with_name("config.json")
    if not original.exists():
        return {}
    try:
        import json

        payload = json.loads(original.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _normalize_testing_config(config: dict) -> dict:
    normalized = dict(config)
    normalized["pad_enabled"] = [True, True, True, True, True]
    try:
        current_gain = float(normalized.get("velocity_gain", 1.0))
    except (TypeError, ValueError):
        current_gain = 1.0
    if current_gain <= 0.0:
        fallback = _original_config().get("velocity_gain", 1.0)
        try:
            fallback_gain = float(fallback)
        except (TypeError, ValueError):
            fallback_gain = 1.0
        normalized["velocity_gain"] = fallback_gain if fallback_gain > 0.0 else 1.0
    return normalized


class TestingMainWindow:
    pass


def _patch_settings_config_path() -> Path:
    settings = _settings_module()
    config_path = _testing_config_path()
    _seed_testing_config(config_path)
    settings.CONFIG_PATH = config_path
    return config_path


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    dll_dir = PROJECT_ROOT / "fluidsynth_dlls"
    env["PATH"] = str(dll_dir) + os.pathsep + env.get("PATH", "")
    env["PYFLUIDSYNTH_LIB"] = str(dll_dir / "libfluidsynth-3.dll")
    env.setdefault("TIMBAL_FS_SAMPLE_RATE", "48000")
    env.setdefault("TIMBAL_FS_PERIOD_SIZE", "64")
    env.setdefault("TIMBAL_FS_PERIODS", "2")
    env.setdefault("TIMBAL_SERIAL_BAUD", "115200")
    env["TIMBAL_CONFIG_PATH"] = str(_testing_config_path())
    try:
        current = _normalize_testing_config(_settings_module().load_config())
    except Exception:
        current = {}
    sf2_path = current.get("last_sf2")
    if isinstance(sf2_path, str) and sf2_path.strip():
        env["TIMBAL_SF2_PATH"] = sf2_path
    for key, env_name in (
        ("sf2_bank", "TIMBAL_SF2_BANK"),
        ("sf2_preset", "TIMBAL_SF2_PRESET"),
    ):
        raw = current.get(key)
        if raw in (None, ""):
            continue
        env[env_name] = str(raw)
    return env


def _spawn_mode(mode_flag: str) -> None:
    subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "main.py"), mode_flag],
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )


def _spawn_original() -> None:
    subprocess.Popen(
        ["cmd.exe", "/c", "run_timbal.bat"],
        cwd=str(PROJECT_ROOT),
        env=_build_env(),
    )


def _handoff_to(window, *, launcher) -> None:
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication, QMessageBox

    try:
        router = getattr(window, "input_router", None)
        if router is not None:
            try:
                router.close()
            except Exception:
                pass
        window.hide()
        window.statusBar().showMessage(
            "Liberando puerto serial y cambiando de herramienta...",
            3000,
        )

        def _launch_and_quit() -> None:
            try:
                launcher()
            except Exception as exc:
                QMessageBox.critical(
                    window,
                    "Error",
                    f"No se pudo abrir la herramienta:\n{exc}",
                )
                window.show()
                return
            app = QApplication.instance()
            if app is not None:
                app.quit()

        QTimer.singleShot(250, _launch_and_quit)
    except Exception as exc:
        QMessageBox.critical(
            window,
            "Error",
            f"No se pudo liberar el puerto para cambiar de herramienta:\n{exc}",
        )


def _enhance_window(window) -> None:
    from PyQt5.QtWidgets import QAction

    window.setWindowTitle("Timbal Digital - Testeo")

    menu_testing = window.menuBar().addMenu("Testeo")

    act_trainer = QAction("Abrir trainer 4/4", window)
    act_trainer.triggered.connect(
        lambda: _handoff_to(window, launcher=lambda: _spawn_mode("--run-trainer"))
    )
    menu_testing.addAction(act_trainer)

    act_analog = QAction("Abrir entrada analog", window)
    act_analog.triggered.connect(
        lambda: _handoff_to(window, launcher=lambda: _spawn_mode("--run-host-analog"))
    )
    menu_testing.addAction(act_analog)

    act_lab = QAction("Abrir Timbal Lab", window)
    act_lab.triggered.connect(
        lambda: _handoff_to(window, launcher=lambda: _spawn_mode("--run-timbal-lab"))
    )
    menu_testing.addAction(act_lab)

    act_original = QAction("Abrir app original", window)
    act_original.triggered.connect(lambda: _handoff_to(window, launcher=_spawn_original))
    menu_testing.addAction(act_original)

    window.statusBar().showMessage(
        "Testeo con config separada. La app original no se toca.",
        8000,
    )


def main() -> None:
    config_path = _patch_settings_config_path()

    from PyQt5.QtWidgets import QMessageBox

    from app.runtime import build_application, build_audio_engine
    from app.state.settings import load_config, save_config
    from app.ui.main_window import MainWindow

    app = build_application()
    config = load_config()

    try:
        engine, resolved = build_audio_engine(config, allow_prompt=True)
    except Exception as exc:
        QMessageBox.critical(None, "Error", f"No se pudo iniciar el motor de audio\n{exc}")
        return

    config = _normalize_testing_config(config)
    config["last_sf2"] = str(resolved)
    save_config(config)

    window = MainWindow(engine, config)
    _enhance_window(window)
    window.resize(1400, 820)
    window.show()

    print(f"[testeo] Config separada: {config_path}")
    print("[testeo] UI principal clonada para testeo.")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
