from multiprocessing import freeze_support
import sys


def main():
    if '--self-test' in sys.argv:
        from app.selftest import run_selftest
        from pathlib import Path
        index = sys.argv.index('--self-test')
        destination = Path(sys.argv[index + 1])
        try:
            run_selftest(destination)
        except Exception:
            import traceback
            destination.mkdir(parents=True, exist_ok=True)
            (destination / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
            return 1
        return 0
    if '--tool' in sys.argv:
        from app.cli import run_cli
        return run_cli(sys.argv[1:])
    from PySide6.QtWidgets import QApplication
    from app.ui.window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName('丸丸小帮手')
    app.setOrganizationName('WanwanTeacherHelper')
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    freeze_support()
    sys.exit(main())
