from pathlib import Path
import json
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QShortcut, QKeySequence
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QListWidget, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QLineEdit, QStackedWidget, QScrollArea, QProgressBar, QMessageBox, QDialog,
    QPlainTextEdit, QDialogButtonBox, QAbstractItemView, QSplitter)
from app.core.contracts import JobRequest
from app.registry import TOOLS
from app.ui.forms import OptionsForm
from app.ui.worker import JobWorker
from app.ui.theme import STYLE


def label(text, name=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        widget.setObjectName(name)
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    if primary:
        widget.setObjectName('primary')
    return widget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('丸丸小帮手 · 离线教师文件助手')
        self.resize(1200, 820)
        self.setMinimumSize(940, 660)
        self.setStyleSheet(STYLE)
        self.setAcceptDrops(True)
        self.paths = []
        self.worker = None
        self.pending = None
        self.last_report = None
        self.preview_text = None
        self.results = ()
        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(central)
        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(204)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 22, 16, 20)
        side.addWidget(label('丸丸小帮手', 'brand'))
        side.addWidget(label('把时间留给孩子', 'tagline'))
        self.nav = QListWidget()
        self.nav.setObjectName('nav')
        self.nav.setAccessibleName('工具导航')
        for index, (title, _, _) in enumerate(TOOLS.values(), 1):
            self.nav.addItem(f'{index:02d}   {title}')
        side.addWidget(self.nav, 1)
        side.addWidget(label('本地处理 · 保留原件\n无需登录，也不上传文件', 'privacy'))
        side.addWidget(button('使用帮助与许可', self.help))
        outer.addWidget(sidebar)
        workspace = QWidget()
        workspace.setObjectName('workspace')
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(14)
        self.title = label('', 'pageTitle')
        self.subtitle = label('', 'subtitle')
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        splitter = QSplitter(Qt.Orientation.Vertical)
        queue_panel = QWidget()
        queue_panel.setObjectName('panel')
        queue_layout = QVBoxLayout(queue_panel)
        queue_layout.setContentsMargins(16, 12, 16, 12)
        toolbar = QHBoxLayout()
        self.queue_title = label('01  添加材料', 'sectionTitle')
        toolbar.addWidget(self.queue_title)
        toolbar.addStretch()
        self.add_button = button('＋ 添加文件', self.add_files)
        self.folder_button = button('添加文件夹', self.add_folder)
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.folder_button)
        queue_layout.addLayout(toolbar)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['文件名', '大小', '状态 / 结果'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setAccessibleName('文件队列，按显示顺序处理')
        self.table.setMinimumHeight(120)
        queue_layout.addWidget(self.table)
        self.empty = label('将文件拖到这里，或点击“添加文件”。原文件始终保留。', 'hint')
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        queue_layout.addWidget(self.empty)
        order = QHBoxLayout()
        self.up_button = button('上移', lambda: self.move(-1))
        self.down_button = button('下移', lambda: self.move(1))
        self.remove_button = button('移出队列', self.remove_selected)
        self.clear_button = button('清空', self.clear_files)
        for widget in [self.up_button, self.down_button, self.remove_button, self.clear_button]:
            order.addWidget(widget)
        order.addStretch()
        queue_layout.addLayout(order)
        splitter.addWidget(queue_panel)
        self.forms = QStackedWidget()
        self.form_widgets = {}
        for key in TOOLS:
            form = OptionsForm(key)
            self.form_widgets[key] = form
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(form)
            self.forms.addWidget(scroll)
        param_panel = QWidget()
        param_panel.setObjectName('panel')
        param_layout = QVBoxLayout(param_panel)
        param_layout.setContentsMargins(16, 12, 16, 12)
        param_layout.addWidget(label('02  设置处理方式', 'sectionTitle'))
        param_layout.addWidget(self.forms)
        splitter.addWidget(param_panel)
        splitter.setSizes([310, 255])
        layout.addWidget(splitter, 1)
        output_row = QHBoxLayout()
        output_row.addWidget(label('保存到'))
        self.output = QLineEdit(str(Path.home() / 'Documents' / '丸丸小帮手输出'))
        self.output.setAccessibleName('输出目录')
        self.output_select = button('选择目录', self.choose_output)
        output_row.addWidget(self.output, 1)
        output_row.addWidget(self.output_select)
        layout.addLayout(output_row)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status = label('准备就绪 · 执行前会展示处理计划', 'hint')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.details_button = button('查看报告', self.show_results)
        self.open_button = button('打开输出目录', self.open_output)
        self.cancel_button = button('取消任务', self.cancel_job)
        self.cancel_button.setEnabled(False)
        self.start_button = button('预览处理计划 →', self.start_preview, True)
        actions.addWidget(self.details_button)
        actions.addWidget(self.open_button)
        actions.addStretch()
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.start_button)
        layout.addLayout(actions)
        outer.addWidget(workspace, 1)
        self.nav.currentRowChanged.connect(self.change_tool)
        self.nav.setCurrentRow(0)
        QShortcut(QKeySequence('Ctrl+O'), self, self.add_files)
        QShortcut(QKeySequence('Delete'), self.table, self.remove_selected)

    def tool_id(self):
        return list(TOOLS)[self.nav.currentRow()]

    def change_tool(self, index):
        key = list(TOOLS)[index]
        self.title.setText(TOOLS[key][0])
        self.subtitle.setText(TOOLS[key][1])
        self.forms.setCurrentIndex(index)

    def is_busy(self):
        return self.worker is not None

    def add_paths(self, paths):
        if self.is_busy():
            return
        known = set(self.paths)
        for path in paths:
            path = Path(path)
            if path.is_symlink() or not path.is_file():
                continue
            path = path.resolve()
            if path not in known and len(self.paths) < 10000:
                self.paths.append(path)
                known.add(path)
        self.refresh_queue()

    def add_files(self):
        if not self.is_busy():
            files, _ = QFileDialog.getOpenFileNames(self, '选择要处理的文件')
            self.add_paths(files)

    def add_folder(self):
        if self.is_busy():
            return
        folder = QFileDialog.getExistingDirectory(self, '添加目录中的文件（不递归子目录）')
        if folder:
            self.add_paths(sorted(Path(folder).iterdir()))

    def refresh_queue(self):
        self.table.setRowCount(len(self.paths))
        for row, path in enumerate(self.paths):
            self.table.setItem(row, 0, QTableWidgetItem(path.name))
            self.table.item(row, 0).setToolTip(str(path))
            size = path.stat().st_size if path.is_file() else 0
            self.table.setItem(row, 1, QTableWidgetItem(f'{size / 1024 / 1024:.2f} MB'))
            self.table.setItem(row, 2, QTableWidgetItem('待处理'))
        self.empty.setVisible(not self.paths)
        self.queue_title.setText(f'01  添加材料  ·  {len(self.paths)} 个文件')

    def remove_selected(self):
        if self.is_busy():
            return
        for row in sorted({item.row() for item in self.table.selectedItems()}, reverse=True):
            del self.paths[row]
        self.refresh_queue()

    def clear_files(self):
        if not self.is_busy():
            self.paths.clear()
            self.refresh_queue()

    def move(self, delta):
        if self.is_busy():
            return
        row = self.table.currentRow()
        if 0 <= row < len(self.paths) and 0 <= row + delta < len(self.paths):
            self.paths[row], self.paths[row + delta] = self.paths[row + delta], self.paths[row]
            self.refresh_queue()
            self.table.selectRow(row + delta)

    def choose_output(self):
        folder = QFileDialog.getExistingDirectory(self, '选择结果保存目录', self.output.text())
        if folder:
            self.output.setText(folder)

    def start_preview(self):
        if self.is_busy():
            return
        if not self.output.text().strip():
            self.status.setText('请选择输出目录')
            return
        key = self.tool_id()
        request = JobRequest(key, tuple(self.paths), Path(self.output.text()).expanduser().resolve(),
                             self.form_widgets[key].options())
        self.launch(request, True)

    def launch(self, request, preview_only=False):
        self.pending = None
        self.worker = JobWorker(request, preview_only, self)
        self.worker.progress.connect(self.on_progress)
        self.worker.completed.connect(self.on_completed)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.on_finished)
        self.set_busy(True)
        self.status.setText('正在生成计划…' if preview_only else '正在处理，请勿移动或修改原文件…')
        self.progress.setRange(0, 0)
        self.worker.start()

    def set_busy(self, busy):
        for widget in [self.nav, self.forms, self.add_button, self.folder_button, self.up_button,
                       self.down_button, self.remove_button, self.clear_button, self.output,
                       self.output_select, self.start_button]:
            widget.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)

    def on_progress(self, progress):
        self.progress.setRange(0, max(progress.total, 1))
        self.progress.setValue(progress.completed)
        self.status.setText(progress.message)

    def on_completed(self, result):
        self.pending = result

    def on_failed(self, message):
        self.status.setText(message)

    def on_finished(self):
        worker = self.worker
        self.worker = None
        self.set_busy(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if self.pending is not None else 0)
        if self.pending is not None:
            if worker.preview_only:
                self.preview_text = self.pending
                self.status.setText('计划已生成，请核对后执行')
                if self.confirm_preview(self.pending):
                    self.launch(worker.request)
            else:
                self.results, self.last_report, report_error = self.pending
                self.display_results()
                if report_error:
                    self.status.setText(self.status.text() + '；报告保存失败：' + report_error)
        worker.deleteLater()

    def confirm_preview(self, text):
        dialog = QDialog(self)
        dialog.setWindowTitle('核对处理计划')
        dialog.resize(760, 560)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label('03  确认后生成新副本', 'sectionTitle'))
        content = QPlainTextEdit(text)
        content.setReadOnly(True)
        layout.addWidget(content)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        actions.button(QDialogButtonBox.StandardButton.Ok).setText('确认并开始')
        actions.button(QDialogButtonBox.StandardButton.Cancel).setText('返回修改')
        actions.accepted.connect(dialog.accept)
        actions.rejected.connect(dialog.reject)
        layout.addWidget(actions)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def display_results(self):
        counts = {status: sum(r.status == status for r in self.results) for status in ('success', 'skipped', 'failed', 'cancelled')}
        self.status.setText(f'完成 {counts["success"]}  ·  无需处理 {counts["skipped"]}  ·  失败 {counts["failed"]}  ·  已取消 {counts["cancelled"]}')
        for result in self.results:
            if result.source in self.paths:
                row = self.paths.index(result.source)
                self.table.setItem(row, 2, QTableWidgetItem(result.message))

    def show_results(self):
        if not self.results:
            self.status.setText('处理完成后可在这里查看逐文件结果与详细报告')
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('处理结果')
        dialog.resize(800, 580)
        layout = QVBoxLayout(dialog)
        text = []
        for result in self.results:
            text += [result.source.name, result.message]
            if result.output:
                text.append(f'输出：{result.output}')
            if result.details:
                text.append(json.dumps(result.details, ensure_ascii=False, indent=2))
        view = QPlainTextEdit('\n\n'.join(text))
        view.setReadOnly(True)
        layout.addWidget(view)
        layout.addWidget(button('关闭', dialog.accept))
        dialog.exec()

    def open_output(self):
        path = Path(self.output.text()).expanduser()
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
        else:
            self.status.setText('输出目录尚不存在；处理后会自动创建')

    def cancel_job(self):
        if self.worker:
            self.worker.cancel.set()
            self.cancel_button.setEnabled(False)
            self.status.setText('正在安全取消，等待当前操作退出…')

    def help(self):
        QMessageBox.information(self, '使用帮助与第三方许可',
            '1. 选择左侧工具并添加文件，队列顺序可调整。\n'
            '2. 设置参数与输出目录，预览后确认执行。\n'
            '3. 打开输出目录复核结果，原件不会被删除或覆盖。\n\n'
            '照片：默认去除 EXIF；透明图片输出 PNG。\n'
            '文档：仅支持无宏/无签名/未加密的 DOCX 与 PPTX。JPEG 优化有损。\n'
            'PDF：不保留书签；表单、签名、注释/链接不处理。\n'
            '表格：首行为字段名；同顺序同字段才汇总。缓存公式值可能过时。\n'
            '模板：固定版式；请复核字体、换行与打印效果。\n'
            '视频：MP4 / MPEG-4 + AAC；实际体积取决于原素材。\n\n'
            '完全离线，无遥测。报告仅在指定目录生成，归档清单包含文件名。\n'
            '依赖 PySide6/Qt (LGPL)、FFmpeg (LGPL) 及其他开源组件。\n'
            '完整许可证、SBOM 与重建说明随 GitHub Release 提供。')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and not self.is_busy():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_paths(url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile())

    def closeEvent(self, event):
        if self.is_busy():
            self.cancel_job()
            self.status.setText('正在取消任务，请待任务停止后再关闭窗口')
            event.ignore()
        else:
            event.accept()
