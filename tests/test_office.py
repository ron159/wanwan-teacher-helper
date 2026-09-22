from io import BytesIO
from threading import Event
from zipfile import ZipFile, ZIP_DEFLATED
import pytest
from PIL import Image
from docx import Document
from app.tools.office import inspect_package, run
from app.core.contracts import JobRequest, OfficeOptions


def test_optimize_changes_only_jpeg_and_keeps_original(tmp_path):
    photo = BytesIO()
    Image.effect_noise((600, 400), 100).convert('RGB').save(photo, 'JPEG', quality=100)
    photo.seek(0)
    document = Document()
    document.add_paragraph('保留 < & > 文字')
    document.add_picture(photo)
    source = tmp_path / '材料.docx'
    document.save(source)
    original = source.read_bytes()
    details = inspect_package(source)
    assert details['categories']['位图']['stored'] > 0
    results = run(JobRequest('office', (source,), tmp_path / 'out', OfficeOptions(True, 75)),
                  lambda p: None, Event())
    assert results[0].status == 'success'
    output = results[0].output
    assert output.stat().st_size < source.stat().st_size
    with ZipFile(source) as before, ZipFile(output) as after:
        assert before.namelist() == after.namelist()
        for name in before.namelist():
            if not name.endswith('.jpg') and not name.endswith('.jpeg'):
                assert before.read(name) == after.read(name)
    assert source.read_bytes() == original
    assert Document(output).paragraphs[0].text == '保留 < & > 文字'


@pytest.mark.parametrize('member', ['../escape', '/abs', 'a\\b', '_xmlsignatures/a.xml', 'word/vbaProject.bin'])
def test_rejects_unsafe_packages(tmp_path, member):
    source = tmp_path / 'bad.docx'
    with ZipFile(source, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr(member, 'bad')
    with pytest.raises(ValueError):
        inspect_package(source)


def test_duplicate_and_bomb_rejected(tmp_path):
    source = tmp_path / 'bomb.docx'
    with ZipFile(source, 'w', ZIP_DEFLATED) as z:
        z.writestr('a', b'0' * 2_000_000)
    with pytest.raises(ValueError):
        inspect_package(source)


def test_no_gain_does_not_publish(tmp_path):
    source = tmp_path / 'small.docx'
    Document().save(source)
    result = run(JobRequest('office', (source,), tmp_path / 'out', OfficeOptions(True)),
                 lambda p: None, Event())
    assert result[0].status == 'skipped'
    assert not list((tmp_path / 'out').glob('*')) if (tmp_path / 'out').exists() else True


def test_duplicate_names_symlink_and_external_entity_rejected(tmp_path):
    from zipfile import ZipInfo
    from app.tools.office import check_zip
    from defusedxml.common import DefusedXmlException
    import warnings
    path = tmp_path / 'malicious.docx'
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with ZipFile(path, 'w') as z:
            z.writestr('same', 'a')
            z.writestr('same', 'b')
    with ZipFile(path) as z, pytest.raises(ValueError):
        check_zip(z)
    info = ZipInfo('link')
    info.create_system = 3
    info.external_attr = 0o120777 << 16
    with ZipFile(path, 'w') as z:
        z.writestr(info, '/etc/passwd')
    with ZipFile(path) as z, pytest.raises(ValueError):
        check_zip(z)
    with ZipFile(path, 'w') as z:
        z.writestr('[Content_Types].xml', '<!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><Types>&x;</Types>')
        z.writestr('_rels/.rels', '<Relationships/>')
        z.writestr('word/document.xml', '<document/>')
    with pytest.raises((ValueError, DefusedXmlException)):
        inspect_package(path)


def test_document_jpeg_metadata_is_not_discarded():
    from app.tools.office import optimized_jpeg
    exif = Image.Exif()
    exif[274] = 6
    buffer = BytesIO()
    Image.new('RGB', (100, 100)).save(buffer, 'JPEG', exif=exif, quality=100)
    assert optimized_jpeg(buffer.getvalue(), 70) is None


def test_complex_jpeg_app_metadata_is_preserved_by_skipping():
    from app.tools.office import optimized_jpeg
    buffer = BytesIO()
    Image.effect_noise((100, 100), 80).convert('RGB').save(buffer, 'JPEG', quality=100)
    raw = buffer.getvalue()
    payload = b'Photoshop 3.0\x00IPTC metadata'
    tagged = raw[:2] + b'\xff\xed' + (len(payload) + 2).to_bytes(2, 'big') + payload + raw[2:]
    assert optimized_jpeg(tagged, 70) is None
