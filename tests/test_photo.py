from threading import Event
from PIL import Image
from app.core.contracts import JobRequest, PhotoOptions
from app.tools.photo import run


def test_rotation_transparency_and_corrupt_isolation(tmp_path):
    source = tmp_path / '原件.jpg'
    exif = Image.Exif()
    exif[274] = 6
    Image.new('RGB', (100, 50), 'red').save(source, exif=exif)
    original = source.read_bytes()
    alpha = tmp_path / '透明.png'
    Image.new('RGBA', (100, 100), (255, 0, 0, 50)).save(alpha)
    broken = tmp_path / 'bad.jpg'
    broken.write_bytes(b'broken')
    result = run(JobRequest('photo', (source, broken, alpha), tmp_path / 'out',
                            PhotoOptions(max_edge=60)), lambda p: None, Event())
    assert [r.status for r in result] == ['success', 'failed', 'success']
    with Image.open(result[0].output) as image:
        assert image.size == (30, 60)
        assert not image.getexif()
    with Image.open(result[2].output) as image:
        assert image.mode == 'RGBA'
    assert source.read_bytes() == original


def test_animation_is_skipped(tmp_path):
    path = tmp_path / 'a.gif'
    Image.new('RGB', (10, 10), 'red').save(path, save_all=True,
        append_images=[Image.new('RGB', (10, 10), 'blue')])
    result = run(JobRequest('photo', (path,), tmp_path / 'out', PhotoOptions()),
                 lambda p: None, Event())
    assert result[0].status == 'skipped'
