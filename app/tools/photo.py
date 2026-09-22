from io import BytesIO
from PIL import Image, ImageOps
from app.core.contracts import FileResult, PhotoOptions
from app.core.jobs import run_files, success, validate_inputs
from app.core.safe_output import SafeOutputWriter, check_cancel, safe_name

MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def load_photo(source):
    image = Image.open(source)
    try:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError('图片超过 4000 万像素上限')
        if getattr(image, 'n_frames', 1) != 1:
            raise ValueError('动画/多帧图片不处理，避免丢失帧')
        if image.mode not in {'RGB', 'RGBA', 'L', 'LA', 'P'}:
            raise ValueError('不支持的色彩模式，请先导出为 RGB 图片')
        image.load()
        result = ImageOps.exif_transpose(image)
        result.info = dict(image.info)
        result.info.pop('exif', None)
        return result
    finally:
        image.close()


def validate_image(path):
    with Image.open(path) as image:
        image.verify()


def normalized_bytes(source, max_edge=1600):
    with load_photo(source) as image:
        image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        with image.convert('RGBA') as rgba, Image.new('RGB', image.size, 'white') as canvas:
            canvas.paste(rgba, mask=rgba.getchannel('A'))
            canvas.save(buffer, format='JPEG', quality=90,
                        icc_profile=image.info.get('icc_profile'))
        buffer.seek(0)
        return buffer


def process(source, request, index, cancel):
    options = request.options
    try:
        image = load_photo(source)
    except ValueError as exc:
        return FileResult(source, None, 'skipped', str(exc), source.stat().st_size)
    with image:
        check_cancel(cancel)
        image.thumbnail((options.max_edge, options.max_edge), Image.Resampling.LANCZOS)
        transparent = image.mode in {'RGBA', 'LA'} or 'transparency' in image.info
        image = image.convert('RGBA' if transparent else 'RGB')
        extension, format_name = ('.png', 'PNG') if transparent else ('.jpg', 'JPEG')
        destination = request.output_dir / f'{options.prefix}_{index:04d}{extension}'
        kwargs = {'icc_profile': image.info.get('icc_profile')}
        if format_name == 'JPEG':
            kwargs.update(quality=options.quality, optimize=True)
        if options.keep_metadata:
            with Image.open(source) as original:
                exif = original.getexif()
                exif.pop(274, None)
                kwargs['exif'] = exif.tobytes()
        with SafeOutputWriter(destination, request.inputs) as writer:
            image.save(writer.path, format=format_name, **kwargs)
            output = writer.commit(validate_image, cancel)
        return success(source, output, '已生成照片副本；保留色彩配置，方向已校正')


def run(request, emit, cancel):
    validate_inputs(request)
    options = request.options
    if not isinstance(options, PhotoOptions) or not 1 <= options.max_edge <= 12000 or not 40 <= options.quality <= 100:
        raise ValueError('照片长边应为 1–12000，质量应为 40–100')
    safe_name(options.prefix)
    return run_files(request, process, emit, cancel)
