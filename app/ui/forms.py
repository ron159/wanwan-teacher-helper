from PySide6.QtWidgets import (QWidget, QFormLayout, QComboBox, QSpinBox, QLineEdit,
                              QPlainTextEdit, QCheckBox, QDoubleSpinBox)
from app.core.contracts import (PhotoOptions, OfficeOptions, OrganizeOptions, PdfOptions,
                                TemplateOptions, SheetOptions, MediaOptions)


def combo(items):
    widget = QComboBox()
    for text, value in items:
        widget.addItem(text, value)
    return widget


def spin(low, high, value):
    widget = QSpinBox()
    widget.setRange(low, high)
    widget.setValue(value)
    return widget


class OptionsForm(QWidget):
    def __init__(self, tool_id):
        super().__init__()
        self.setObjectName('optionsForm')
        self.tool_id = tool_id
        self.fields = {}
        self.form = QFormLayout(self)
        self.form.setSpacing(12)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        if tool_id == 'photo':
            self.add('preset', '用途预设', combo([('文档插图 · 1920 px', 1920), ('家长分享 · 1280 px', 1280), ('打印准备 · 3000 px', 3000)]))
            self.add('max_edge', '最长边（像素）', spin(1, 12000, 1920))
            self.fields['preset'].currentIndexChanged.connect(lambda: self.fields['max_edge'].setValue(self.fields['preset'].currentData()))
            self.add_direction_fields()
            self.add('quality', 'JPEG 质量', spin(40, 100, 85))
            self.add('prefix', '命名前缀', QLineEdit('照片'))
            self.add('keep_metadata', '照片元数据', QCheckBox('保留 EXIF（可能含位置）'))
        elif tool_id == 'office':
            self.add('optimize', '处理方式', combo([('保守瘦身 · 先诊断再确认', True),
                                              ('激进瘦身 · 图片缩小与强压缩', 'aggressive'),
                                              ('只诊断占用', False)]))
            self.add('quality', 'JPEG 质量', spin(40, 95, 85))
            self.fields['optimize'].currentIndexChanged.connect(self.update_office_quality)
        elif tool_id == 'organize':
            self.add('mode', '整理方式', combo([('分类复制', 'classify'), ('批量命名副本', 'rename'), ('完全重复报告', 'duplicates'), ('学期 ZIP 归档', 'archive')]))
            self.add('prefix', '命名前缀', QLineEdit('材料'))
        elif tool_id == 'template':
            self.add('layout', '选择模板', combo([('A4 照片材料 · Word', 'photo_docx'), ('照片课件 · PowerPoint', 'photo_pptx'), ('通知', 'notice'), ('周计划', 'week'), ('姓名标签 / 座位卡', 'labels'), ('奖状', 'certificate')]))
            self.add('rows', '每页行数', spin(1, 10, 3))
            self.add('columns', '每页列数', spin(1, 10, 2))
            self.add('page_orientation', 'A4 纸张方向', combo([('纵向', 'portrait'), ('横向', 'landscape')]))
            self.add('image_size_mode', '图片尺寸', combo([('自动适配网格（等比例）', 'auto'), ('手动设置宽高（厘米）', 'manual')]))
            for key, text, value in [('image_width_cm', '图片宽度（厘米）', 7), ('image_height_cm', '图片高度（厘米）', 5)]:
                field = QDoubleSpinBox()
                field.setRange(.1, 30)
                field.setDecimals(2)
                field.setSingleStep(.1)
                field.setValue(value)
                self.add(key, text, field)
            keep = QCheckBox('等比例适配所填宽高；取消则拉伸至指定尺寸')
            keep.setChecked(True)
            self.add('keep_aspect_ratio', '手动尺寸比例', keep)
            self.fields['image_size_mode'].currentIndexChanged.connect(self.update_photo_fields)
            self.add_direction_fields()
            self.fields['layout'].currentIndexChanged.connect(self.update_photo_fields)
            self.update_photo_fields()
            self.add('title', '标题', QLineEdit('活动记录'))
            self.add('class_name', '班级', QLineEdit())
            self.add('date', '日期', QLineEdit())
            body = QPlainTextEdit()
            body.setPlaceholderText('填写真实内容；周计划每行一项，例如：周一：观察落叶')
            body.setMaximumHeight(100)
            self.add('body', '正文 / 说明', body)
            names = QPlainTextEdit()
            names.setPlaceholderText('姓名标签、奖状使用，每行一位')
            names.setMaximumHeight(70)
            self.add('names', '姓名列表', names)
        elif tool_id == 'pdf':
            self.add('mode', '页面操作', combo([('按队列顺序合并', 'merge'), ('逐页拆分', 'split'), ('抽取并重排页面', 'extract'), ('旋转选定页', 'rotate'), ('照片转 A4 PDF', 'images')]))
            pages = QLineEdit()
            pages.setPlaceholderText('例如 1,3-5；留空为全部')
            self.add('pages', '页码（从 1 开始）', pages)
            self.add('rotation', '顺时针旋转', combo([('90°', 90), ('180°', 180), ('270°', 270)]))
        elif tool_id == 'sheet':
            name = QLineEdit()
            name.setPlaceholderText('留空使用各文件首个工作表')
            self.add('sheet_name', '工作表名称', name)
            self.add('formula_policy', '遇到公式', combo([('拒绝，避免结果失真', 'reject'), ('读取已保存的缓存值', 'cached')]))
        elif tool_id == 'media':
            self.add('mode', '输出方式', combo([('压缩视频 · MP4', 'video'), ('提取音频 · M4A', 'audio'), ('导出音频 · WAV', 'wav')]))
            self.add('max_height', '最高画面高度', combo([('720p · 分享', 720), ('1080p · 清晰', 1080), ('480p · 小体积', 480)]))
            self.add('quality', '视频质量（低值更清晰）', spin(2, 15, 5))
            for key, label in [('start', '开始时间（秒）'), ('duration', '保留时长（0 = 到结尾）')]:
                field = QDoubleSpinBox()
                field.setRange(0, 86400)
                field.setDecimals(2)
                self.add(key, label, field)

    def add_direction_fields(self):
        self.add('rotation', '批量顺时针旋转', combo([('不额外旋转（自动校正 EXIF）', 0), ('90°', 90), ('180°', 180), ('270°', 270)]))
        self.add('orientation', '旋转后统一方向', combo([('保持横竖方向', 'original'), ('统一横向（竖图顺时针转 90°）', 'landscape'), ('统一竖向（横图顺时针转 90°）', 'portrait')]))

    def update_photo_fields(self):
        layout = self.fields['layout'].currentData()
        for key in ('rows', 'columns', 'page_orientation', 'image_size_mode'):
            self.form.setRowVisible(self.fields[key], layout == 'photo_docx')
        manual = layout == 'photo_docx' and self.fields['image_size_mode'].currentData() == 'manual'
        for key in ('image_width_cm', 'image_height_cm', 'keep_aspect_ratio'):
            self.form.setRowVisible(self.fields[key], manual)
        for key in ('rotation', 'orientation'):
            self.form.setRowVisible(self.fields[key], layout.startswith('photo_'))

    def update_office_quality(self):
        aggressive = self.fields['optimize'].currentData() == 'aggressive'
        quality = self.fields['quality']
        quality.setRange(25 if aggressive else 40, 95)
        quality.setValue(45 if aggressive else 85)

    def add(self, key, label, widget):
        widget.setAccessibleName(label)
        self.fields[key] = widget
        self.form.addRow(label, widget)

    def options(self):
        values = {}
        for key, widget in self.fields.items():
            if key == 'preset':
                continue
            if isinstance(widget, QComboBox):
                value = widget.currentData()
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                value = widget.value()
            elif isinstance(widget, QPlainTextEdit):
                value = widget.toPlainText()
            else:
                value = widget.text().strip()
            values[key] = value
        if self.tool_id == 'office':
            values['aggressive'] = values['optimize'] == 'aggressive'
            values['optimize'] = bool(values['optimize'])
        cls = {'photo': PhotoOptions, 'office': OfficeOptions, 'organize': OrganizeOptions,
               'template': TemplateOptions, 'pdf': PdfOptions, 'sheet': SheetOptions, 'media': MediaOptions}[self.tool_id]
        return cls(**values)
