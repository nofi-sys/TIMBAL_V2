#!/usr/bin/env python3
"""Compatibilidad con la UI legacy: delega en la nueva ventana."""

from app.ui.main_window import run_new_ui


def main() -> None:
    run_new_ui()


if __name__ == "__main__":
    main()
