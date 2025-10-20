
import sys, argparse

def main():
    parser = argparse.ArgumentParser(description="Timbal Digital (legacy/new UI)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--legacy-ui", action="store_true", help="Iniciar la UI tradicional.")
    group.add_argument("--new-ui", action="store_true", help="Iniciar la UI nueva (refactor).")
    args = parser.parse_args()

    if args.legacy_ui or not args.new_ui:
        from legacy.legacy_app import main as legacy_main
        legacy_main()
    else:
        from app.ui.main_window import run_new_ui
        run_new_ui()

if __name__ == "__main__":
    main()
