from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette

from app.ui.window import MainWindow


def test_dark_combo_popup_and_form_have_readable_colors(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.apply_theme(Qt.ColorScheme.Dark)
    window.show()
    window.nav.setCurrentRow(1)
    combo = window.form_widgets['office'].fields['optimize']
    combo.showPopup()
    qtbot.wait(20)
    popup = combo.view()
    assert popup.palette().color(QPalette.ColorRole.Text).lightness() > 180
    assert popup.palette().color(QPalette.ColorRole.Base).lightness() < 100
    assert window.form_widgets['office'].palette().color(QPalette.ColorRole.Window).lightness() < 100
    combo.hidePopup()


def test_office_mode_sets_aggressive_quality(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    form = window.form_widgets['office']
    form.fields['optimize'].setCurrentIndex(1)
    options = form.options()
    assert options.optimize and options.aggressive and options.quality == 45
    form.fields['optimize'].setCurrentIndex(2)
    assert not form.options().optimize
