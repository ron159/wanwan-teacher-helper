from docx import Document
from docx.shared import Cm, Pt
from docx.oxml.ns import qn
from pptx import Presentation
from pptx.util import Inches, Pt as PptPt
from app.core.contracts import TemplateOptions, Progress
from app.core.jobs import validate_inputs, success
from app.core.safe_output import SafeOutputWriter, check_cancel
from app.tools.photo import normalized_bytes
from PIL import Image

LAYOUTS = {'notice', 'week', 'labels', 'certificate', 'photo_docx', 'photo_pptx'}


def validate_options(options):
    if not isinstance(options, TemplateOptions) or options.layout not in LAYOUTS:
        raise ValueError('未知材料模板')
    for text, limit, label in [(options.title, 40, '标题'), (options.class_name, 30, '班级'),
                                (options.date, 40, '日期'), (options.body, 1500, '正文')]:
        if len(text) > limit or any(ord(c) < 32 and c not in '\n\t' for c in text):
            raise ValueError(f'{label}过长或包含不可用字符，上限 {limit} 字')
    if not options.title.strip():
        raise ValueError('请填写标题')
    if options.layout in {'notice', 'week'} and not options.body.strip():
        raise ValueError('请填写正文/周计划，不会自动编造内容')
    names = [line.strip() for line in options.names.splitlines() if line.strip()]
    if options.layout in {'labels', 'certificate'} and not names:
        raise ValueError('请填写姓名，每行一位')
    if options.layout.startswith('photo_') and len(options.body) > 180:
        raise ValueError('照片说明最多 180 字，请精简后生成')
    if any(any(ord(c) < 32 for c in name) for name in names):
        raise ValueError('姓名包含不可用控制字符')
    if len(names) > 200 or any(len(name) > 20 for name in names):
        raise ValueError('最多 200 位姓名，每位不超过 20 字')
    return names


def run(request, emit, cancel):
    options = request.options
    names = validate_options(options)
    photos = options.layout.startswith('photo_')
    validate_inputs(request, allow_empty=not photos)
    if photos and len(request.inputs) > 200:
        raise ValueError('照片材料单次最多 200 张')
    check_cancel(cancel)
    ppt = options.layout == 'photo_pptx'
    extension = '.pptx' if ppt else '.docx'
    if ppt:
        document = Presentation()
        document.slide_width = Inches(13.333)
        document.slide_height = Inches(7.5)
        for index, source in enumerate(request.inputs, 1):
            check_cancel(cancel)
            slide = document.slides.add_slide(document.slide_layouts[6])
            heading = slide.shapes.add_textbox(Inches(.6), Inches(.3), Inches(12), Inches(.7))
            heading.text_frame.text = options.title
            heading.text_frame.paragraphs[0].font.size = PptPt(28)
            data = normalized_bytes(source)
            with Image.open(data) as image:
                width, height = image.size
            data.seek(0)
            scale = min(11 / width, 5.5 / height)
            slide.shapes.add_picture(data, Inches((13.333 - width * scale) / 2), Inches(1.25),
                                     width=Inches(width * scale), height=Inches(height * scale))
            footer = slide.shapes.add_textbox(Inches(.6), Inches(6.9), Inches(12), Inches(.4))
            footer.text_frame.text = f'{options.class_name}  {options.date}  ·  {index}'
            emit(Progress(index, len(request.inputs), '正在生成照片课件'))
    else:
        document = Document()
        section = document.sections[0]
        section.page_width, section.page_height = Cm(21), Cm(29.7)
        section.top_margin = section.bottom_margin = Cm(1.8)
        section.left_margin = section.right_margin = Cm(2)
        style = document.styles['Normal']
        style.font.name = 'Microsoft YaHei'
        style.font.size = Pt(11)
        style.element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
        document.add_heading(options.title, 0)
        document.add_paragraph(f'{options.class_name}    {options.date}')
        if options.layout == 'photo_docx':
            for index, source in enumerate(request.inputs, 1):
                check_cancel(cancel)
                if index > 1:
                    document.add_page_break()
                data = normalized_bytes(source)
                with Image.open(data) as image:
                    w, h = image.size
                data.seek(0)
                scale = min(16 / w, 18 / h)
                document.add_picture(data, width=Cm(w * scale), height=Cm(h * scale))
                document.add_paragraph(f'照片 {index}' + (f' · {options.body}' if options.body else ''))
                emit(Progress(index, len(request.inputs), '正在生成 A4 照片材料'))
        elif options.layout == 'labels':
            table = document.add_table(rows=0, cols=2)
            table.style = 'Table Grid'
            for index in range(0, len(names), 2):
                check_cancel(cancel)
                cells = table.add_row().cells
                for cell, name in zip(cells, names[index:index + 2]):
                    cell.text = f'\n{name}\n{options.class_name}\n'
        elif options.layout == 'certificate':
            for index, name in enumerate(names):
                check_cancel(cancel)
                if index:
                    document.add_page_break()
                    document.add_heading(options.title, 0)
                document.add_heading(name, 1)
                document.add_paragraph(options.body or '请由教师填写真实的表彰事由。')
                document.add_paragraph(f'{options.class_name}\n{options.date}')
        elif options.layout == 'week':
            table = document.add_table(rows=1, cols=2)
            table.style = 'Table Grid'
            table.rows[0].cells[0].text = '项目'
            table.rows[0].cells[1].text = '计划内容'
            for index, line in enumerate(options.body.splitlines(), 1):
                check_cancel(cancel)
                cells = table.add_row().cells
                parts = line.replace('：', ':').split(':', 1)
                cells[0].text = parts[0] if len(parts) == 2 else str(index)
                cells[1].text = parts[-1]
        else:
            for line in options.body.splitlines():
                document.add_paragraph(line)
    with SafeOutputWriter(request.output_dir / f'材料成品{extension}', request.inputs) as writer:
        document.save(writer.path)
        output = writer.commit(lambda p: Presentation(p) if ppt else Document(p), cancel)
    source = request.inputs[0] if request.inputs else request.output_dir
    return (success(source, output, '固定模板已生成；请复核分页、字体和打印效果'),)
