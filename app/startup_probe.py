"""Explicit release acceptance command; never enabled during ordinary launches."""
from pathlib import Path
import ctypes
import json
import os
import sys
import time
import tempfile
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.ui.window import MainWindow


def run_startup_probe(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()

    def write_report():
        ui_ready = time.time()
        default_output = Path(window.output.text())
        existed = default_output.exists()
        default_output.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryFile(dir=default_output) as probe:
                probe.write(b'write acceptance')
                probe.flush()
                os.fsync(probe.fileno())
        finally:
            if not existed:
                default_output.rmdir()
        bundle = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else None
        payload = {'ui_ready_unix': ui_ready, 'frozen': bool(bundle),
                   'default_output_directory': str(default_output), 'default_output_writable': True,
                   'bundle_bytes': sum(p.stat().st_size for p in bundle.rglob('*') if p.is_file()) if bundle else 0,
                   'is_admin': ctypes.windll.shell32.IsUserAnAdmin() != 0 if os.name == 'nt' else os.geteuid() == 0}
        (output / 'startup-probe.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    def ready():
        code = 0
        try:
            write_report()
        except Exception as exc:
            (output / 'startup-failure.txt').write_text(f'{type(exc).__name__}: {exc}', encoding='utf-8')
            code = 1
        finally:
            window.close()
            app.exit(code)

    QTimer.singleShot(100, ready)
    return app.exec()
