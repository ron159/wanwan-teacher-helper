from io import BytesIO
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PIL import Image
from app.tools.photo import load_photo, orient_photo
from app.core.jobs import friendly_error


def preview_images(source, options):
    with load_photo(source) as image:
        original_size = image.size
        before = image.copy()
        before.thumbnail((560, 420), Image.Resampling.LANCZOS)
        first = BytesIO()
        before.save(first, 'PNG')
        before.close()
        image = orient_photo(image, options.rotation, options.orientation)
        image.thumbnail((options.max_edge, options.max_edge), Image.Resampling.LANCZOS)
        prepared_size = image.size
        transparent = image.mode in {'RGBA', 'LA'} or 'transparency' in image.info
        encoded = BytesIO()
        image.convert('RGBA' if transparent else 'RGB').save(
            encoded, 'PNG' if transparent else 'JPEG', quality=options.quality)
        image.close()
        encoded.seek(0)
        with Image.open(encoded) as after:
            after.thumbnail((560, 420), Image.Resampling.LANCZOS)
            second = BytesIO()
            after.save(second, 'PNG')
        return first.getvalue(), second.getvalue(), original_size, prepared_size


class PreviewWorker(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, source, options, parent):
        super().__init__(parent)
        self.source, self.options = source, options

    def run(self):
        try:
            self.ready.emit(preview_images(self.source, self.options))
        except Exception as exc:
            self.failed.emit(friendly_error(exc))


class PhotoPreviewDialog(QDialog):
    def __init__(self, source, options, parent):
        super().__init__(parent)
        self.setWindowTitle('照片效果预览 · 不写入文件')
        self.resize(1000, 570)
        layout = QVBoxLayout(self)
        self.status = QLabel('正在读取照片…')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        panes = QHBoxLayout()
        self.before, self.after = QLabel('原图'), QLabel('处理后')
        for pane in (self.before, self.after):
            pane.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pane.setMinimumSize(300, 300)
            pane.setObjectName('photoPane')
            panes.addWidget(pane)
        layout.addLayout(panes, 1)
        close = QPushButton('关闭')
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.worker = PreviewWorker(source, options, self)
        self.worker.ready.connect(self.display)
        self.worker.failed.connect(self.status.setText)
        self.worker.start()

    def display(self, result):
        before, after, original_size, prepared_size = result
        self.before.setPixmap(QPixmap.fromImage(QImage.fromData(before)))
        self.after.setPixmap(QPixmap.fromImage(QImage.fromData(after)))
        self.status.setText(f'左：方向校正后的原图 {original_size[0]} × {original_size[1]}   '
                            f'右：处理效果 {prepared_size[0]} × {prepared_size[1]}（缩略预览）')

    def done(self, result):
        if not self.worker.isRunning():
            super().done(result)
        else:
            self.status.setText('正在生成预览，请稍后关闭')
