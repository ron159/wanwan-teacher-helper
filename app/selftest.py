"""End-to-end smoke suite shipped in the executable; synthetic data only."""
from dataclasses import asdict
from pathlib import Path
from threading import Event
import hashlib
import json
import subprocess
import time
from PIL import Image
from docx import Document
from openpyxl import Workbook
from pypdf import PdfWriter
from app.core.contracts import (JobRequest, PhotoOptions, OfficeOptions, OrganizeOptions,
    TemplateOptions, PdfOptions, SheetOptions, MediaOptions)
from app.registry import TOOLS
from app.tools.media import engines


def run_selftest(root: Path):
    started = time.monotonic()
    root.mkdir(parents=True, exist_ok=True)
    source_dir = root / '中文输入'
    source_dir.mkdir(exist_ok=True)
    photo = source_dir / '活动照片.jpg'
    Image.effect_noise((800, 600), 80).convert('RGB').save(photo, quality=100)
    doc = Document()
    doc.add_paragraph('离线烟测材料 < & >')
    doc.add_picture(str(photo))
    document = source_dir / '材料.docx'
    doc.save(document)
    sheet = source_dir / '名册.xlsx'
    workbook = Workbook()
    workbook.active.append(['编号', '姓名'])
    workbook.active.append(['001', '测试材料'])
    workbook.save(sheet)
    pdf = source_dir / '测试.pdf'
    writer = PdfWriter()
    writer.add_blank_page(300, 400)
    writer.add_blank_page(400, 500)
    writer.write(pdf)
    ffmpeg, _ = engines()
    video = source_dir / '活动视频.avi'
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=12',
                    '-f', 'lavfi', '-i', 'sine=frequency=440', '-t', '1', '-c:v', 'rawvideo',
                    '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', str(video)], check=True,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cases = [
        ('photo', (photo,), PhotoOptions()),
        ('office', (document,), OfficeOptions(True, 75)),
        ('organize', (photo, document), OrganizeOptions('archive')),
        ('organize', (photo, photo), OrganizeOptions('duplicates')),
        ('template', (photo,), TemplateOptions('photo_docx')),
        ('template', (photo,), TemplateOptions('photo_pptx')),
        ('pdf', (pdf,), PdfOptions('extract', '2,1')),
        ('pdf', (photo,), PdfOptions('images')),
        ('sheet', (sheet, sheet), SheetOptions()),
        ('media', (video,), MediaOptions()),
        ('media', (video,), MediaOptions('audio')),
    ]
    originals = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_dir.iterdir()}
    records = []
    for index, (tool, inputs, options) in enumerate(cases):
        result = TOOLS[tool][2](JobRequest(tool, inputs, root / f'output-{index}', options),
                              lambda progress: None, Event())
        if not result or any(r.status != 'success' for r in result):
            raise RuntimeError(f'Smoke test failed: {tool}: {result}')
        records.extend(asdict(r) for r in result)
    for path, digest in originals.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError('An original file was modified')
    # GUI startup from the same frozen application verifies Qt plugins/resources.
    from PySide6.QtWidgets import QApplication
    from app.ui.window import MainWindow
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    for index in range(7):
        window.nav.setCurrentRow(index)
        application.processEvents()
    window.nav.setCurrentRow(0)
    application.processEvents()
    window.grab().save(str(root / 'ui.png'))
    window.close()
    (root / 'self-test.json').write_text(json.dumps({'status': 'passed', 'cases': len(cases),
        'elapsed_seconds': round(time.monotonic() - started, 2), 'originals_unchanged': True,
        'results': records}, default=str, ensure_ascii=False, indent=2), encoding='utf-8')
