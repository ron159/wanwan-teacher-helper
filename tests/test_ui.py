from PIL import Image
from app.ui.window import MainWindow
from PySide6.QtCore import Qt


def test_photo_user_flow_and_all_navigation(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    for i in range(7):
        window.nav.setCurrentRow(i)
        assert window.forms.currentIndex() == i
        assert window.title.text()
    window.nav.setCurrentRow(0)
    image = tmp_path / '活动.jpg'
    Image.new('RGB', (100, 100), 'red').save(image)
    window.add_paths([image])
    window.output.setText(str(tmp_path / 'out'))
    monkeypatch.setattr(window, 'confirm_preview', lambda text: True)
    qtbot.mouseClick(window.start_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: bool(window.results) and not window.is_busy(), timeout=10000)
    assert window.results[0].status == 'success'
    assert window.results[0].output.is_file()
    assert window.last_report.is_file()
    assert window.start_button.isEnabled()


def test_queue_order_and_no_execution_without_confirmation(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    paths = [tmp_path / 'a.txt', tmp_path / 'b.txt']
    for path in paths:
        path.write_text('hello')
    window.add_paths(paths)
    window.table.selectRow(1)
    window.move(-1)
    assert window.paths == list(reversed(paths))
    window.nav.setCurrentRow(2)
    window.output.setText(str(tmp_path / 'out'))
    monkeypatch.setattr(window, 'confirm_preview', lambda text: False)
    window.start_preview()
    qtbot.waitUntil(lambda: not window.is_busy(), timeout=10000)
    assert not (tmp_path / 'out').exists()
