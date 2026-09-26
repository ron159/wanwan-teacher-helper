"""Desktop contact book for students and their family contacts."""

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QStandardPaths
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app.contacts import (CONTACT_LIMIT, FIELDS, ContactStore, blank_contact,
                          contact_key, filter_contacts, parse_excel, parse_text)


EXAMPLE = ('学生姓名：张三 父亲姓名：张明 父亲电话：13800138000 '
           '母亲姓名：李梅 母亲电话：13900139000\n'
           '学生姓名：李四 家长姓名：李华 家长电话：13700137000')


def plain(text, name=None):
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        label.setObjectName(name)
    return label


def action(text, callback, primary=False):
    widget = QPushButton(text)
    if primary:
        widget.setObjectName('primary')
    widget.clicked.connect(callback)
    return widget


class ContactEditor(QDialog):
    def __init__(self, contact, parent=None):
        super().__init__(parent)
        self.setWindowTitle('编辑家长联系方式' if contact else '添加学生及家长')
        self.resize(560, 620)
        layout = QVBoxLayout(self)
        layout.addWidget(plain(self.windowTitle(), 'sectionTitle'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName('contactsEditorBody')
        form = QFormLayout(body)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.fields = {}
        current = contact or blank_contact()
        for key, title in FIELDS.items():
            if key in {'address', 'notes'}:
                widget = QPlainTextEdit(current[key])
                widget.setFixedHeight(70 if key == 'address' else 95)
            else:
                widget = QLineEdit(current[key])
            widget.setAccessibleName(title)
            self.fields[key] = widget
            form.addRow(title, widget)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        footer = QHBoxLayout()
        self.delete_button = action('删除', lambda: None)
        self.delete_button.setVisible(contact is not None)
        footer.addWidget(self.delete_button)
        footer.addStretch()
        footer.addWidget(action('取消', self.reject))
        self.save_button = action('保存联系方式', lambda: None, True)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)

    def values(self):
        return {key: (widget.toPlainText() if isinstance(widget, QPlainTextEdit)
                      else widget.text()).strip() for key, widget in self.fields.items()}


class ContactsPage(QWidget):
    def __init__(self, store_path=None, parent=None):
        super().__init__(parent)
        if store_path is None:
            store_path = Path(QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation)) / 'contacts.json'
        self.store = ContactStore(store_path)
        self.contacts = []
        self.pending = []
        self.issues = []
        self.paste_was_visible = False
        self.load_failed = False
        self.setObjectName('contactsPage')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(13)
        layout.addWidget(plain('通信簿', 'pageTitle'))
        layout.addWidget(plain('学生与家长联系方式 · 仅保存在当前电脑', 'subtitle'))

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('搜索学生、家长、电话或住址')
        self.search.setAccessibleName('搜索联系人')
        self.search.textChanged.connect(self.refresh)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(action('清除', self.search.clear))
        layout.addLayout(search_row)

        toolbar = QHBoxLayout()
        self.import_button = action('导入 Excel', self.choose_excel, True)
        self.paste_button = action('粘贴识别', self.toggle_paste)
        self.add_button = action('添加学生', self.add_contact)
        self.edit_button = action('编辑选中', self.edit_selected)
        self.delete_button = action('删除选中', self.delete_selected)
        for widget in (self.import_button, self.paste_button, self.add_button,
                       self.edit_button, self.delete_button):
            toolbar.addWidget(widget)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        layout.addWidget(plain('支持 .xlsx / .xls（不超过 2 MB）；导入前可预览，原文保留在备注。', 'hint'))

        self.paste_panel = QWidget()
        self.paste_panel.setObjectName('panel')
        paste_layout = QVBoxLayout(self.paste_panel)
        paste_layout.addWidget(plain('粘贴学生与家长信息', 'sectionTitle'))
        paste_layout.addWidget(plain('每行一位学生；号码默认作为家长电话。也可粘贴 Excel 表头与多行数据。', 'hint'))
        self.paste_text = QPlainTextEdit()
        self.paste_text.setPlaceholderText('例如：张三 13800138000\n学生姓名：李四 母亲：李梅 13900139000')
        self.paste_text.setAccessibleName('待识别联系人文本')
        self.paste_text.setFixedHeight(115)
        paste_layout.addWidget(self.paste_text)
        paste_actions = QHBoxLayout()
        paste_actions.addWidget(action('查看可识别格式与示例', self.show_recognition_help))
        paste_actions.addStretch()
        paste_actions.addWidget(action('识别并预览', self.recognize_text, True))
        paste_layout.addLayout(paste_actions)
        self.paste_panel.hide()
        layout.addWidget(self.paste_panel)

        self.preview_panel = QWidget()
        self.preview_panel.setObjectName('panel')
        preview_layout = QVBoxLayout(self.preview_panel)
        self.preview_title = plain('', 'sectionTitle')
        preview_layout.addWidget(self.preview_title)
        self.preview_details = QPlainTextEdit()
        self.preview_details.setReadOnly(True)
        self.preview_details.setFixedHeight(140)
        self.preview_details.setAccessibleName('导入预览与识别问题')
        preview_layout.addWidget(self.preview_details)
        preview_actions = QHBoxLayout()
        preview_actions.addStretch()
        preview_actions.addWidget(action('取消导入', lambda: self.cancel_preview()))
        self.confirm_button = action('确认保存', self.confirm_import, True)
        preview_actions.addWidget(self.confirm_button)
        preview_layout.addLayout(preview_actions)
        self.preview_panel.hide()
        layout.addWidget(self.preview_panel)

        self.count = plain('', 'sectionTitle')
        layout.addWidget(self.count)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['学生', '家长联系方式', '家庭住址'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().resizeSection(0, 150)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setAccessibleName('学生与家长通信簿；双击编辑')
        self.table.itemDoubleClicked.connect(lambda _: self.edit_selected())
        self.table.itemSelectionChanged.connect(self.update_selection)
        layout.addWidget(self.table, 1)
        self.message = plain('', 'hint')
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        try:
            self.contacts = self.store.load()
        except (OSError, ValueError, TypeError) as exc:
            self.load_failed = True
            self.message.setText(f'通信簿读取失败，请修复存储文件后重试，避免覆盖原有数据：{exc}')
            for widget in (self.import_button, self.paste_button, self.add_button):
                widget.setEnabled(False)
        self.refresh()

    def update_selection(self):
        enabled = not self.load_failed and bool(self.table.selectedItems())
        self.edit_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def selected_contact(self):
        row = self.table.currentRow()
        if row < 0 or not self.table.selectedItems() or not self.table.item(row, 0):
            return None
        contact_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return next((contact for contact in self.contacts if contact['id'] == contact_id), None)

    def refresh(self):
        selected = self.selected_contact()
        matches = filter_contacts(self.contacts, self.search.text())
        self.table.clearSelection()
        self.table.setRowCount(len(matches))
        for row, contact in enumerate(matches):
            people = []
            for title, name_key, phone_key in [('父亲', 'father', 'fatherPhone'),
                                               ('母亲', 'mother', 'motherPhone'),
                                               ('家长1', 'guardian', 'phone'),
                                               ('家长2', 'guardian2', 'guardian2Phone')]:
                if contact[name_key] or contact[phone_key]:
                    people.append(f'{title} {contact[name_key]}  {contact[phone_key] or "未填写电话"}'.strip())
            cells = [contact['name'] or '待补充学生姓名',
                     '\n'.join(people) or '暂未填写家长电话', contact['address']]
            for col, value in enumerate(cells):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, contact['id'])
                self.table.setItem(row, col, item)
            self.table.setRowHeight(row, min(92, max(38, 20 * max(1, len(people)) + 8)))
            if selected and selected['id'] == contact['id']:
                self.table.selectRow(row)
        self.count.setText(f'{"搜索结果" if self.search.text().strip() else "学生名单"}  ·  {len(matches)} / {len(self.contacts)} 人')
        if not matches and not self.load_failed:
            self.message.setText('没有找到匹配的学生或家长' if self.search.text().strip()
                                 else '通信簿还是空的：导入表格、粘贴信息或手动添加学生。')
        elif matches and self.message.text().startswith(('没有找到', '通信簿还是')):
            self.message.clear()
        self.update_selection()

    def toggle_paste(self):
        if not self.pending:
            self.paste_panel.setVisible(self.paste_panel.isHidden())

    def show_recognition_help(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle('识别格式示例')
        dialog.setText('每位学生一行，手机号须为11位。\n\n' + EXAMPLE +
                       '\n\nExcel 表头可使用：学生姓名、家长1姓名、家长1电话、家长2姓名、家长2电话、家庭住址。'
                       '\n不知道父母关系时请使用家长1/2，并在预览中核对。')
        copy_button = dialog.addButton('复制示例', QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton('返回修改', QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is copy_button:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(EXAMPLE)

    def recognize_text(self):
        content = self.paste_text.toPlainText()
        if len(content) > 50000:
            self.message.setText('粘贴内容超过 50000 字，请分批识别。')
            return
        self.prepare_preview(parse_text(content), '粘贴内容')

    def choose_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, '导入通信簿', '', 'Excel 表格 (*.xlsx *.xls)')
        if path:
            self.import_excel_path(path)

    def import_excel_path(self, path):
        if self.load_failed or self.pending:
            return
        try:
            result = parse_excel(path)
        except Exception as exc:
            self.pending = []
            self.preview_panel.hide()
            self.message.setText(f'无法读取表格：{exc}。请使用未加密且未损坏的 Excel 文件。')
            self.show_recognition_help()
            return
        summary = f'读取 {result.sheets} 个工作表，跳过 {result.skipped} 行'
        if result.no_headers:
            summary += f'；{result.no_headers} 个表未找到标准表头，已按文本识别'
        self.prepare_preview(result, summary)

    def prepare_preview(self, result, summary):
        self.pending = []
        self.preview_panel.hide()
        self.issues = result.issues
        seen = {contact_key(contact) for contact in self.contacts}
        duplicates = 0
        for contact in result.contacts:
            key = contact_key(contact)
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)
                self.pending.append(contact)
        if len(self.pending) + len(self.contacts) > CONTACT_LIMIT:
            self.pending = []
            self.message.setText(f'超过通信簿 {CONTACT_LIMIT} 条上限，请拆分或减少内容。')
            return
        if not result.contacts:
            self.message.setText('未识别到学生与家长信息，请参考格式示例修改。')
        elif not self.pending:
            self.message.setText('识别的记录均已存在，无需重复导入。')
        else:
            self.paste_was_visible = not self.paste_panel.isHidden()
            self.paste_panel.hide()
            self.import_button.setEnabled(False)
            self.paste_button.setEnabled(False)
            self.preview_title.setText(f'待导入 {len(self.pending)} 位学生')
            lines = [f'{summary}；排除 {duplicates} 条完全重复记录。',
                     '以下展示前 10 条；识别结果可能有误，请核对后保存。']
            for contact in self.pending[:10]:
                people = '；'.join(f'{title} {contact[name]} {contact[phone]}' for title, name, phone in
                                  [('父亲', 'father', 'fatherPhone'), ('母亲', 'mother', 'motherPhone'),
                                   ('家长1', 'guardian', 'phone'), ('家长2', 'guardian2', 'guardian2Phone')]
                                  if contact[name] or contact[phone])
                lines.append(f'{contact["name"] or "待补充学生姓名"}：{people}  {contact["address"]}')
            if self.issues:
                lines.append(f'有 {len(self.issues)} 条内容需要核对：')
                lines.extend(self.issues[:5])
            self.preview_details.setPlainText('\n'.join(lines))
            self.confirm_button.setText(f'确认保存 {len(self.pending)} 条')
            self.preview_panel.show()
            self.message.clear()
        if not result.contacts or self.issues:
            self.show_recognition_help()

    def cancel_preview(self, restore_paste=True):
        self.pending = []
        self.issues = []
        self.preview_panel.hide()
        self.import_button.setEnabled(not self.load_failed)
        self.paste_button.setEnabled(not self.load_failed)
        if restore_paste and self.paste_was_visible:
            self.paste_panel.show()
        self.paste_was_visible = False

    def persist(self, contacts):
        if self.load_failed:
            return False
        try:
            self.store.save(contacts)
        except (OSError, ValueError) as exc:
            self.message.setText(f'保存失败，已有数据未改变：{exc}')
            return False
        self.contacts = contacts
        self.refresh()
        return True

    def confirm_import(self):
        if not self.pending:
            return
        seen = {contact_key(contact) for contact in self.contacts}
        added = []
        for contact in self.pending:
            if contact_key(contact) not in seen:
                added.append({'id': uuid4().hex, **contact})
                seen.add(contact_key(contact))
        if self.persist([*self.contacts, *added]):
            needs_correction = bool(self.issues)
            self.cancel_preview(restore_paste=needs_correction)
            if not needs_correction:
                self.paste_text.clear()
            self.message.setText(f'已保存 {len(added)} 条；请核对识别结果与原文。')

    def add_contact(self):
        self.open_editor()

    def edit_selected(self):
        contact = self.selected_contact()
        if contact:
            self.open_editor(contact)

    def open_editor(self, contact=None):
        if self.load_failed:
            return
        dialog = ContactEditor(contact, self)

        def save():
            values = dialog.values()
            if not any(values[key] for key in FIELDS if key not in {'address', 'notes'}):
                QMessageBox.warning(dialog, '无法保存', '请至少填写学生姓名或家长姓名、电话。')
                return
            record = {'id': contact['id'] if contact else uuid4().hex, **values}
            updated = ([record if item['id'] == record['id'] else item for item in self.contacts]
                       if contact else [*self.contacts, record])
            if self.persist(updated):
                self.message.setText('已保存联系方式。')
                dialog.accept()
            else:
                QMessageBox.warning(dialog, '保存失败', self.message.text())

        def delete():
            if self.confirm_delete(contact):
                dialog.accept()

        dialog.save_button.clicked.connect(save)
        if contact:
            dialog.delete_button.clicked.connect(delete)
        dialog.exec()

    def confirm_delete(self, contact):
        if QMessageBox.question(self, '删除联系人', f'确定删除“{contact["name"] or "这条记录"}”吗？',
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return False
        if self.persist([item for item in self.contacts if item['id'] != contact['id']]):
            self.message.setText('已删除联系人。')
            return True
        return False

    def delete_selected(self):
        contact = self.selected_contact()
        if contact:
            self.confirm_delete(contact)
