"""Explicit release acceptance command; never enabled during ordinary launches."""
from pathlib import Path
import ctypes
import json
import os
import sys
import time
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.ui.window import MainWindow


def run_startup_probe(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()

    def ready():
        bundle = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else None
        payload = {'ui_ready_unix': time.time(), 'frozen': bool(bundle),
                   'bundle_bytes': sum(p.stat().st_size for p in bundle.rglob('*') if p.is_file()) if bundle else 0,
                   'is_admin': ctypes.windll.shell32.IsUserAnAdmin() != 0 if os.name == 'nt' else os.geteuid() == 0}
        (output / 'startup-probe.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
        window.close()
        app.quit()

    QTimer.singleShot(100, ready)
    return app.exec()
