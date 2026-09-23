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


def test_template_transparency_composites_on_white(tmp_path):
    from app.tools.photo import normalized_bytes
    path = tmp_path / 'transparent.png'
    Image.new('RGBA', (10, 10), (0, 0, 0, 0)).save(path)
    with Image.open(normalized_bytes(path)) as result:
        assert min(result.getpixel((5, 5))) > 245


def test_preview_uses_selected_dimensions_without_writing(tmp_path):
    from app.ui.photo_preview import preview_images
    path = tmp_path / 'source.jpg'
    Image.new('RGB', (400, 300)).save(path)
    original = path.read_bytes()
    before, after, original_size, prepared = preview_images(path, PhotoOptions(max_edge=200))
    assert before and after and original_size == (400, 300) and prepared == (200, 150)
    assert path.read_bytes() == original and len(list(tmp_path.iterdir())) == 1


def test_real_srgb_profile_survives_resize(tmp_path):
    from PIL import ImageCms
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    source = tmp_path / 'profile.jpg'
    Image.new('RGB', (300, 200), 'red').save(source, icc_profile=profile)
    result = run(JobRequest('photo', (source,), tmp_path / 'out', PhotoOptions(max_edge=100)),
                 lambda p: None, Event())
    assert result[0].status == 'success'
    with Image.open(result[0].output) as output:
        assert output.info['icc_profile'] == profile
        assert output.size == (100, 67)
