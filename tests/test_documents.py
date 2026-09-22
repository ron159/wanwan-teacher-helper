from threading import Event
import pytest
from PIL import Image
from pypdf import PdfWriter, PdfReader
from openpyxl import Workbook, load_workbook
from docx import Document
from pptx import Presentation
from app.core.contracts import JobRequest, PdfOptions, SheetOptions, TemplateOptions
from app.tools import pdf, sheet, template


def test_pdf_merge_extract_rotate_split(tmp_path):
    source = tmp_path / 'a.pdf'
    writer = PdfWriter()
    for i in range(3):
        writer.add_blank_page(width=300 + i, height=400)
    writer.write(source)
    for options, count in [(PdfOptions('merge'), 3), (PdfOptions('extract', '3,1'), 2),
                            (PdfOptions('rotate', '2', 90), 3)]:
        result = pdf.run(JobRequest('pdf', (source,), tmp_path / 'out', options), lambda p: None, Event())
        pages = PdfReader(result[0].output).pages
        assert len(pages) == count
        if options.mode == 'extract':
            assert pages[0].mediabox.width == 302
        if options.mode == 'rotate':
            assert pages[1].rotation == 90 and pages[0].rotation == 0
    result = pdf.run(JobRequest('pdf', (source,), tmp_path / 'out', PdfOptions('split')),
                     lambda p: None, Event())
    assert len(result) == 3 and all(len(PdfReader(r.output).pages) == 1 for r in result)
    with pytest.raises(ValueError):
        pdf.parse_pages('0,99', 3)


def test_sheet_preserves_ids_and_rejects_mismatch_formula(tmp_path):
    files = (tmp_path / 'a.xlsx', tmp_path / 'b.xlsx')
    for path in files:
        wb = Workbook()
        wb.active.append(['编号', '姓名'])
        wb.active.append(['001', '张同学'])
        wb.save(path)
    req = JobRequest('sheet', files, tmp_path / 'out', SheetOptions())
    result = sheet.run(req, lambda p: None, Event())
    wb = load_workbook(result[0].output)
    assert wb.active.max_row == 3 and wb.active['A2'].value == '001'
    wb.close()
    wb = Workbook()
    wb.active.append(['错误字段'])
    wb.save(files[1])
    with pytest.raises(ValueError):
        sheet.run(req, lambda p: None, Event())
    wb = Workbook()
    wb.active.append(['编号', '姓名'])
    wb.active.append(['=1+1', '姓名'])
    wb.save(files[1])
    with pytest.raises(ValueError):
        sheet.run(req, lambda p: None, Event())


@pytest.mark.parametrize('layout', ['notice', 'week', 'labels', 'certificate', 'photo_docx', 'photo_pptx'])
def test_controlled_templates(tmp_path, layout):
    image = tmp_path / 'photo.jpg'
    Image.new('RGB', (100, 200), 'red').save(image)
    options = TemplateOptions(layout, '春游 & 分享', '小一班', '2026-09-23',
                              '周一：观察树叶\n周二：手工', '张同学\n李同学')
    result = template.run(JobRequest('template', (image,), tmp_path / 'out', options),
                          lambda p: None, Event())
    assert result[0].output.is_file()
    if layout == 'photo_pptx':
        assert len(Presentation(result[0].output).slides) == 1
    else:
        assert Document(result[0].output).paragraphs[0].text == options.title
