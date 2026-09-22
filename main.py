from multiprocessing import freeze_support
import sys


def main():
    if '--self-test' in sys.argv:
        from app.selftest import run_selftest
        from pathlib import Path
        index = sys.argv.index('--self-test')
        run_selftest(Path(sys.argv[index + 1]))
        return 0
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
