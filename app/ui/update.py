"""Background network work for the startup updater."""

from PySide6.QtCore import QThread, Signal

from app.updater import download_update, find_update


class UpdateWorker(QThread):
    found = Signal(object)
    downloaded = Signal(object, str)
    progress = Signal(int, int)
    failed = Signal(str)

    def __init__(self, version=None, update=None, parent=None):
        super().__init__(parent)
        self.version = version
        self.update = update

    def run(self):
        try:
            if self.update is None:
                result = find_update(self.version)
                if not self.isInterruptionRequested():
                    self.found.emit(result)
            else:
                def report(done, total):
                    if self.isInterruptionRequested():
                        raise RuntimeError('更新下载已取消')
                    self.progress.emit(done, total)
                path, digest = download_update(self.update, report)
                if not self.isInterruptionRequested():
                    self.downloaded.emit(path, digest)
                else:
                    path.unlink(missing_ok=True)
                    path.parent.rmdir()
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
