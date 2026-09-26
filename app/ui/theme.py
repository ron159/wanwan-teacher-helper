def theme_style(dark):
    if dark:
        text, background, panel, input_bg = '#e7f1e9', '#151e1b', '#202c26', '#29372f'
        sidebar, muted, border = '#102b24', '#b1c5b8', '#536b5b'
        hover, pressed, selection = '#354b3d', '#45604a', '#3b7056'
        selected_text, table_alt, header = '#ffffff', '#26342c', '#304036'
        disabled, progress_bg = '#91a597', '#35463a'
    else:
        text, background, panel, input_bg = '#263d38', '#f4f6f2', '#ffffff', '#ffffff'
        sidebar, muted, border = '#183f37', '#576e64', '#bdcfc2'
        hover, pressed, selection = '#eaf1e5', '#d9e7d3', '#e0edde'
        selected_text, table_alt, header = '#183f37', '#f6f8f3', '#eef3e9'
        disabled, progress_bg = '#87968b', '#e0e8dd'
    return f'''
QWidget {{ color: {text}; font-family: "Microsoft YaHei", "PingFang SC", sans-serif; font-size: 13px; }}
QMainWindow, QDialog, QMessageBox, #workspace, #contactsPage {{ background: {background}; }}
#sidebar {{ background: {sidebar}; border: 0; }}
#brand {{ color: #ffffff; font-size: 23px; font-weight: 700; padding: 12px 8px; }}
#nav {{ background: transparent; border: 0; outline: 0; color: #dce9e0; font-size: 15px; }}
#nav::item {{ padding: 15px 16px; margin: 3px 0; border-radius: 6px; }}
#nav::item:selected {{ background: #dcebc9; color: #183f37; font-weight: 600; }}
#nav::item:hover:!selected {{ background: #285347; }}
#privacy {{ color: #c5d8cc; padding: 8px; }}
#pageTitle {{ font-size: 27px; font-weight: 700; }}
#subtitle, #hint {{ color: {muted}; }}
#sectionTitle {{ font-size: 15px; font-weight: 600; }}
#panel {{ background: {panel}; border: 1px solid {border}; border-radius: 8px; }}
QPushButton {{ color: {text}; background: {input_bg}; border: 1px solid {border}; border-radius: 5px; padding: 8px 14px; }}
QPushButton:hover {{ background: {hover}; }}
QPushButton:pressed {{ background: {pressed}; }}
QPushButton:focus {{ border: 2px solid #56a67c; }}
QPushButton:disabled {{ color: {disabled}; background: {panel}; border-color: {border}; }}
QPushButton#primary {{ background: #23664f; color: #ffffff; border: 0; font-weight: 600; padding: 11px 22px; }}
QPushButton#primary:hover {{ background: #174f3b; }}
QPushButton#primary:disabled {{ background: #597463; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{ color: {text}; background: {input_bg}; border: 1px solid {border}; border-radius: 4px; padding: 6px; selection-background-color: {selection}; selection-color: {selected_text}; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: #56a67c; }}
QComboBox::drop-down {{ border-left: 1px solid {border}; width: 24px; }}
QComboBox QAbstractItemView {{ color: {text}; background: {input_bg}; border: 1px solid {border}; selection-background-color: {selection}; selection-color: {selected_text}; outline: 0; }}
QCheckBox {{ color: {text}; spacing: 8px; }}
QTableWidget {{ color: {text}; border: 0; background: {panel}; alternate-background-color: {table_alt}; gridline-color: {border}; selection-background-color: {selection}; selection-color: {selected_text}; }}
QHeaderView::section {{ color: {text}; background: {header}; padding: 9px; border: 0; border-bottom: 1px solid {border}; font-weight: 600; }}
QProgressBar {{ border: 0; background: {progress_bg}; border-radius: 4px; min-height: 8px; max-height: 8px; }}
QProgressBar::chunk {{ background: #4f8968; border-radius: 4px; }}
QScrollArea, QScrollArea QWidget#qt_scrollarea_viewport, QWidget#optionsForm, QWidget#contactsEditorBody {{ border: 0; background: {panel}; }}
QScrollBar:vertical {{ background: {panel}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: {panel}; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QLabel#photoPane {{ background: {panel}; border: 1px solid {border}; }}
QToolTip {{ background: {sidebar}; color: white; border: 0; padding: 6px; }}
'''
