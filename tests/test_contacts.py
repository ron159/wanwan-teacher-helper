from pathlib import Path
import json

import pytest
from openpyxl import Workbook
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from app.contacts import (ContactStore, blank_contact, contact_key, extract_phones,
                          filter_contacts, parse_excel, parse_rows, parse_text)
from app.ui.contacts import ContactEditor, ContactsPage
from app.ui.window import MainWindow


def test_text_recognition_keeps_student_and_guardian_roles():
    assert extract_phones('+86 138-0013-8000 / １３９００１３９０００') == '13800138000 / 13900139000'
    row = parse_text('学生姓名：张三 父亲：张明 电话：13800138000 电话：13700137000 '
                     '母亲：李梅 电话：13900139000').contacts[0]
    assert row['name'] == '张三'
    assert row['fatherPhone'] == '13800138000 / 13700137000'
    assert row['motherPhone'] == '13900139000'
    assert row['phone'] == ''
    generic = parse_text('学生姓名：李四 家长1姓名：李华 家长1电话：13800138000 '
                         '家长2姓名：王梅 家长2电话：13900139000').contacts[0]
    assert generic['name'] == '李四'
    assert generic['guardian'] == '李华'
    assert generic['guardian2Phone'] == '13900139000'
    assert generic['father'] == ''


def test_multiline_and_table_recognition_reports_bad_records():
    result = parse_text('学生姓名：张三\n父亲：张明\n联系电话：13800138000\n'
                        '家庭住址：幸福路1号\n\n李四 13900139000\n无效内容')
    assert len(result.contacts) == 2
    assert result.contacts[0]['fatherPhone'] == '13800138000'
    assert result.contacts[0]['address'] == '幸福路1号'
    assert result.skipped == 1 and result.issues
    rows = parse_rows([
        ['学生姓名', '父亲', '', '母亲', ''],
        ['', '姓名', '手机', '姓名', '手机'],
        ['小明', '张明', 13800138000.0, '李梅', 13900139000.0],
    ])
    assert rows.contacts[0]['name'] == '小明'
    assert rows.contacts[0]['fatherPhone'] == '13800138000'
    assert rows.contacts[0]['motherPhone'] == '13900139000'
    invalid = parse_rows([['学生姓名', '家长电话'], ['张三', '12345']])
    assert invalid.contacts[0]['phone'] == ''
    assert '12345' in invalid.contacts[0]['notes']
    assert invalid.issues
    relation = parse_rows([['学生姓名', '家长1姓名', '家长1电话', '与学生关系'],
                           ['张三', '张明', 13800138000, '父亲']]).contacts[0]
    assert relation['father'] == '张明' and relation['fatherPhone'] == '13800138000'
    assert relation['guardian'] == ''


def test_pasted_excel_headers_search_and_deduplication():
    result = parse_text('学生姓名\t家长姓名\t家长电话\t家庭住址\n'
                        '张三\t李梅\t13900139000\t幸福路1号')
    assert result.contacts[0]['guardian'] == '李梅'
    assert result.contacts[0]['address'] == '幸福路1号'
    first = {'id': '1', **result.contacts[0]}
    second = {**first, 'id': '2', 'name': '张四'}
    assert filter_contacts([first, second], '李梅 9000') == [first, second]
    assert filter_contacts([first, second], '幸福 张四') == [second]
    assert contact_key(first) == contact_key({**first, 'notes': '来自另一个文件'})
    assert contact_key(first) != contact_key(second)


def test_xlsx_and_xls_import(tmp_path):
    book = Workbook()
    sheet = book.active
    sheet.title = '通信簿'
    sheet.append(['学生姓名', '父亲姓名', '父亲电话', '母亲姓名', '母亲电话', '家庭住址'])
    sheet.append(['张三', '张明', 13800138000, '李梅', 13900139000, '幸福路1号'])
    xlsx = tmp_path / 'contacts.xlsx'
    book.save(xlsx)
    for path in (xlsx, Path(__file__).parent / 'fixtures' / 'contacts.xls'):
        result = parse_excel(path)
        assert result.sheets == 1 and not result.issues
        assert result.contacts[0]['fatherPhone'] == '13800138000'
        assert result.contacts[0]['motherPhone'] == '13900139000'
        assert result.contacts[0]['address'] == '幸福路1号'


def test_excel_import_refuses_rows_that_would_be_silently_truncated(tmp_path):
    book = Workbook()
    sheet = book.active
    sheet.append(['学生姓名', '家长电话'])
    for _ in range(1033):
        sheet.append(['张三', 13800138000])
    path = tmp_path / 'too-many.xlsx'
    book.save(path)
    with pytest.raises(ValueError, match='行数'):
        parse_excel(path)


def test_store_preserves_old_data_and_refuses_corruption(tmp_path):
    path = tmp_path / 'contacts.json'
    store = ContactStore(path)
    old = {'id': 'old', **{key: value for key, value in blank_contact().items()
                          if key not in {'guardian', 'guardian2', 'guardian2Phone'}}}
    old['name'] = '张三'
    path.write_text(json.dumps([old]), encoding='utf-8')
    assert store.load()[0]['guardian2'] == ''
    loaded = store.load()
    store.save(loaded)
    assert store.load() == loaded
    path.write_text('{broken', encoding='utf-8')
    with pytest.raises(ValueError):
        store.load()
    assert path.read_text(encoding='utf-8') == '{broken'


def test_contacts_page_preview_save_search_and_failure(qtbot, tmp_path, monkeypatch):
    page = ContactsPage(tmp_path / 'contacts.json')
    qtbot.addWidget(page)
    monkeypatch.setattr(page, 'show_recognition_help', lambda: None)
    page.paste_text.setPlainText('张三 13800138000\n李四 13900139000')
    page.toggle_paste()
    page.recognize_text()
    assert len(page.pending) == 2
    assert page.preview_panel.isHidden() is False
    assert page.paste_panel.isHidden()
    assert not page.import_button.isEnabled()
    page.cancel_preview()
    assert not page.paste_panel.isHidden()
    assert page.import_button.isEnabled()
    page.recognize_text()
    page.confirm_import()
    assert len(page.store.load()) == 2
    page.search.setText('1390')
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == '李四'
    page.search.clear()
    page.table.selectRow(0)
    page.search.setText('李四')
    assert page.selected_contact() is None  # A filtered row must not inherit another student's selection.
    page.search.clear()
    page.paste_text.setPlainText('张三 13800138000')
    page.recognize_text()
    assert not page.pending
    page.paste_text.setPlainText('王五 13700137000')
    page.recognize_text()
    monkeypatch.setattr(page.store, 'save', lambda _: (_ for _ in ()).throw(OSError('disk full')))
    page.confirm_import()
    assert len(page.contacts) == 2 and len(page.pending) == 1
    assert '保存失败' in page.message.text()
    page.paste_text.setPlainText('内容' * 25001)
    page.recognize_text()
    assert '超过 50000 字' in page.message.text()


def test_contacts_editor_and_navigation(qtbot, tmp_path, monkeypatch):
    from PySide6.QtCore import QStandardPaths
    monkeypatch.setattr(QStandardPaths, 'writableLocation', lambda _: str(tmp_path))
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.nav.setCurrentRow(7)
    assert window.contacts_page.isVisible()
    assert not window.workspace.isVisible()
    assert window.tool_id() is None
    page = window.contacts_page

    def complete_editor():
        dialog = next(widget for widget in page.findChildren(ContactEditor) if widget.isVisible())
        dialog.fields['name'].setText('张三')
        dialog.fields['mother'].setText('李梅')
        dialog.fields['motherPhone'].setText('13900139000')
        dialog.save_button.click()

    QTimer.singleShot(0, complete_editor)
    page.add_contact()
    assert page.contacts[0]['motherPhone'] == '13900139000'
    page.table.selectRow(0)

    def edit_address():
        dialog = next(widget for widget in page.findChildren(ContactEditor) if widget.isVisible())
        dialog.fields['address'].setPlainText('幸福路1号')
        dialog.save_button.click()

    QTimer.singleShot(0, edit_address)
    page.edit_selected()
    assert page.store.load()[0]['address'] == '幸福路1号'
    page.table.selectRow(0)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    page.delete_selected()
    assert page.contacts == []
    window.nav.setCurrentRow(0)
    assert window.workspace.isVisible()


def test_corrupt_contact_file_disables_edits(qtbot, tmp_path):
    path = tmp_path / 'contacts.json'
    path.write_text('not-json', encoding='utf-8')
    page = ContactsPage(path)
    qtbot.addWidget(page)
    assert page.load_failed
    assert not page.add_button.isEnabled()
    assert not page.persist([{'id': '1', **blank_contact()}])
    assert path.read_text(encoding='utf-8') == 'not-json'


def test_failed_recognition_opens_example_and_preserves_pasted_text(qtbot, tmp_path, monkeypatch):
    page = ContactsPage(tmp_path / 'contacts.json')
    qtbot.addWidget(page)
    shown = []
    monkeypatch.setattr(page, 'show_recognition_help', lambda: shown.append(True))
    page.paste_text.setPlainText('请老师查收\n12345')
    page.recognize_text()
    assert shown == [True]
    assert not page.pending
    assert '请老师查收' in page.paste_text.toPlainText()
    assert '未识别到' in page.message.text()
