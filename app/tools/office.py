"""Conservative package editing: unchanged parts are hashed, never reserialized."""
from collections import defaultdict
from copy import copy
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED, is_zipfile
import hashlib
import stat
from defusedxml import ElementTree
from PIL import Image
from app.core.contracts import FileResult, OfficeOptions
from app.core.jobs import run_files, success, validate_inputs
from app.core.safe_output import SafeOutputWriter, check_cancel
from app.tools.photo import MAX_PIXELS

MAX_MEMBER = 256 * 1024 * 1024
MAX_TOTAL = 2 * 1024**3
MAX_XML = 16 * 1024 * 1024
MAX_JPEG = 32 * 1024 * 1024


def check_zip(archive, cancel=None):
    infos = archive.infolist()
    if len(infos) > 20000:
        raise ValueError('包内成员过多')
    names = set()
    total = 0
    for info in infos:
        if cancel:
            check_cancel(cancel)
        path = PurePosixPath(info.filename)
        if (info.filename in names or not info.filename or path.is_absolute()
                or '..' in path.parts or '\\' in info.filename or ':' in info.filename
                or '\x00' in info.filename or stat.S_ISLNK(info.external_attr >> 16)):
            raise ValueError('ZIP 含重复成员、越界路径或符号链接')
        names.add(info.filename)
        total += info.file_size
        if (info.file_size > MAX_MEMBER or total > MAX_TOTAL
                or info.file_size / max(info.compress_size, 1) > 250):
            raise ValueError('ZIP 展开容量或压缩比超过安全上限')
        if info.flag_bits & 1 or info.compress_type not in {ZIP_STORED, ZIP_DEFLATED}:
            raise ValueError('加密或不支持的 ZIP 压缩方式')
    return infos


def category(name):
    suffix = PurePosixPath(name).suffix.lower()
    if suffix in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff'}:
        return '位图'
    if suffix in {'.svg', '.emf', '.wmf'}:
        return '矢量图'
    if suffix in {'.mp4', '.avi', '.mov', '.wmv', '.mp3', '.wav', '.m4a', '.wma'}:
        return '影音'
    if '/fonts/' in name or suffix in {'.odttf', '.fntdata', '.ttf'}:
        return '字体'
    if '/embeddings/' in name:
        return '嵌入对象'
    if suffix in {'.xml', '.rels'}:
        return 'XML/关系'
    return '其他'


def inspect_package(source, cancel=None):
    if source.suffix.lower() not in {'.pptx', '.docx'}:
        raise ValueError('仅支持无宏 .pptx / .docx；旧格式请先另存为新格式')
    if not is_zipfile(source):
        raise ValueError('不是有效的 OOXML ZIP，可能已加密或损坏')
    categories = defaultdict(lambda: {'stored': 0, 'expanded': 0})
    candidates = []
    external_links = 0
    with ZipFile(source) as archive:
        infos = check_zip(archive, cancel)
        names = {info.filename for info in infos}
        main = 'word/document.xml' if source.suffix.lower() == '.docx' else 'ppt/presentation.xml'
        if not {'[Content_Types].xml', '_rels/.rels', main} <= names:
            raise ValueError('缺少 OOXML 核心成员，扩展名与内容不匹配')
        for info in infos:
            if cancel:
                check_cancel(cancel)
            lower = info.filename.lower()
            if any(s in lower for s in ('_xmlsignatures', 'vbaproject', 'vbadata', 'signature')):
                raise ValueError('不处理含签名或宏的文档')
            bucket = categories[category(lower)]
            bucket['stored'] += info.compress_size
            bucket['expanded'] += info.file_size
            if lower.endswith(('.xml', '.rels')):
                if info.file_size > MAX_XML:
                    raise ValueError('XML 成员超过安全上限')
                data = archive.read(info)
                try:
                    root = ElementTree.fromstring(data)
                except Exception as exc:
                    raise ValueError('文档含非法 XML 或外部实体') from exc
                if info.filename == '[Content_Types].xml':
                    for node in root:
                        content_type = node.get('ContentType', '').lower()
                        if any(x in content_type for x in ('macroenabled', 'vbaproject', 'signature')):
                            raise ValueError('不处理含签名或宏的文档')
                if lower.endswith('.rels'):
                    external_links += sum(node.get('TargetMode') == 'External' for node in root)
            else:
                # Stream every member to verify CRC with bounded memory.
                with archive.open(info) as stream:
                    while stream.read(1024 * 1024):
                        if cancel:
                            check_cancel(cancel)
            if lower.startswith(('word/media/', 'ppt/media/')) and lower.endswith(('.jpg', '.jpeg')):
                candidates.append(info.filename)
    stored = sum(v['stored'] for v in categories.values())
    return {'categories': dict(categories), 'container_overhead': source.stat().st_size - stored,
            'jpeg_candidates': candidates, 'external_links': external_links,
            'largest': [{'part': i.filename, 'stored': i.compress_size} for i in
                        sorted(infos, key=lambda i: i.compress_size, reverse=True)[:10]]}


def optimized_jpeg(data, quality):
    if len(data) > MAX_JPEG:
        return None
    try:
        with Image.open(BytesIO(data)) as image:
            if (image.format != 'JPEG' or image.mode not in {'RGB', 'L'}
                    or getattr(image, 'n_frames', 1) != 1
                    or image.width * image.height > MAX_PIXELS
                    or image.getexif() or image.info.get('icc_profile')
                    or image.info.get('xmp') or image.info.get('comment')):
                return None
            for marker, payload in image.applist:
                if (marker != 'APP0' or not payload.startswith(b'JFIF\0')
                        or len(payload) != 14 or payload[7] not in {0, 1}
                        or payload[12:] != b'\0\0'
                        or (payload[7] == 0 and payload[8:12] != b'\0\1\0\1')):
                    return None
            image.load()
            buffer = BytesIO()
            image.save(buffer, 'JPEG', quality=quality, optimize=True, subsampling='keep',
                       dpi=image.info.get('dpi', (0, 0)))
            result = buffer.getvalue()
            return result if len(result) < len(data) else None
    except Exception:
        return None


def stream_copy(source, target, cancel):
    digest = hashlib.sha256()
    while chunk := source.read(1024 * 1024):
        check_cancel(cancel)
        digest.update(chunk)
        if target:
            target.write(chunk)
    return digest.hexdigest()


def process(source, request, index, cancel):
    details = inspect_package(source, cancel)
    if not request.options.optimize:
        return FileResult(source, None, 'success', '诊断完成；未修改文档',
                          source.stat().st_size, details=details)
    hashes, changed = {}, []
    destination = request.output_dir / f'{source.stem[:90]}_精简{source.suffix.lower()}'
    with SafeOutputWriter(destination, request.inputs) as writer:
        with ZipFile(source) as before, ZipFile(writer.path, 'w') as after:
            after.comment = before.comment
            for info in before.infolist():
                check_cancel(cancel)
                replacement = None
                if info.filename in details['jpeg_candidates'] and info.file_size <= MAX_JPEG:
                    replacement = optimized_jpeg(before.read(info), request.options.quality)
                cloned = copy(info)
                if replacement:
                    after.writestr(cloned, replacement)
                    hashes[info.filename] = hashlib.sha256(replacement).hexdigest()
                    changed.append(info.filename)
                else:
                    with before.open(info) as src, after.open(cloned, 'w') as dst:
                        hashes[info.filename] = stream_copy(src, dst, cancel)
        if not changed or writer.path.stat().st_size >= source.stat().st_size:
            return FileResult(source, None, 'skipped', '无需优化：无可安全缩小的 JPEG 或整体体积未减小',
                              source.stat().st_size, details=details)

        def verify(path):
            with ZipFile(path) as archive:
                if archive.namelist() != list(hashes):
                    raise ValueError('输出成员集合改变')
                for info in archive.infolist():
                    with archive.open(info) as stream:
                        if stream_copy(stream, None, cancel) != hashes[info.filename]:
                            raise ValueError('输出成员校验失败')
                    if info.filename in changed:
                        with Image.open(BytesIO(archive.read(info))) as image:
                            image.verify()
        output = writer.commit(verify, cancel)
    details['changed'] = changed
    return success(source, output, f'已优化 {len(changed)} 张 JPEG；其余部件内容一致，请复核画面', details)


def run(request, emit, cancel):
    validate_inputs(request)
    if not isinstance(request.options, OfficeOptions) or not 40 <= request.options.quality <= 95:
        raise ValueError('文档 JPEG 质量应为 40–95')
    return run_files(request, process, emit, cancel)
