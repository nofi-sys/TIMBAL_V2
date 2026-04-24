
import sys, argparse

def main():
    parser = argparse.ArgumentParser(description="Timbal Digital (legacy/new UI)")
    parser.add_argument("--run-dino", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--run-trainer", action="store_true", help="Iniciar el entrenador ritmico 4/4.")
    parser.add_argument("--run-host-analog", action="store_true", help="Iniciar el experimento host-side analogico.")
    parser.add_argument("--run-timbal-lab", action="store_true", help="Iniciar el laboratorio experimental del timbal.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--legacy-ui", action="store_true", help="Iniciar la UI tradicional (fallback).")
    group.add_argument("--new-ui", action="store_true", help="Iniciar la UI nueva (refactor).")
    args = parser.parse_args()

    if args.run_dino:
        from rhythm_dino_game import main as dino_main
        dino_main()
        return
    if args.run_trainer:
        from app.trainer.window import run_trainer_window
        run_trainer_window()
        return
    if args.run_host_analog:
        from app.host_analog.window import run_host_analog_window
        run_host_analog_window()
        return
    if args.run_timbal_lab:
        from app.timbal_lab.ui.window import run_timbal_lab_window
        run_timbal_lab_window()
        return

    if args.legacy_ui:
        print("[launcher] Iniciando UI legacy (--legacy-ui)")
        from legacy.legacy_app import main as legacy_main
        legacy_main()
    else:
        print("[launcher] Iniciando UI nueva (default)")
        from app.ui.main_window import run_new_ui
        run_new_ui()

if __name__ == "__main__":
    main()
