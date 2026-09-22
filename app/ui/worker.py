from threading import Event
from PySide6.QtCore import QThread, Signal
from app.registry import TOOLS, preview
from app.core.jobs import friendly_error
from app.core.reports import write_report
from app.core.safe_output import Cancelled


class JobWorker(QThread):
    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, request, preview_only=False, parent=None):
        super().__init__(parent)
        self.request = request
        self.preview_only = preview_only
        self.cancel = Event()

    def run(self):
        try:
            if self.preview_only:
                self.completed.emit(preview(self.request, self.progress.emit, self.cancel))
            else:
                results = TOOLS[self.request.tool_id][2](self.request, self.progress.emit, self.cancel)
                report = None
                report_error = None
                try:
                    report = write_report(self.request.output_dir, self.request.tool_id, results)
                except Exception as exc:
                    report_error = friendly_error(exc)
                self.completed.emit((results, report, report_error))
        except Cancelled:
            self.failed.emit('任务已取消；已完成的副本保留，当前临时文件已清理')
        except Exception as exc:
            self.failed.emit(friendly_error(exc))
