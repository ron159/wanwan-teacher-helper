from contextlib import ExitStack
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from PIL import Image
from app.core.contracts import PdfOptions, Progress, FileResult
from app.core.jobs import validate_inputs, success, friendly_error
from app.core.safe_output import SafeOutputWriter, check_cancel, Cancelled
from app.tools.photo import load_photo


def parse_pages(text, count):
    if not text.strip():
        return list(range(count))
    result = []
    try:
        for part in text.replace('，', ',').split(','):
            bounds = [int(x.strip()) for x in part.split('-')]
            if len(bounds) == 1:
                result.append(bounds[0] - 1)
            elif len(bounds) == 2 and bounds[0] <= bounds[1] and bounds[1] - bounds[0] <= count:
                result.extend(range(bounds[0] - 1, bounds[1]))
            else:
                raise ValueError()
        if not result or len(result) > 5000 or any(i < 0 or i >= count for i in result):
            raise ValueError()
    except ValueError as exc:
        raise ValueError('页码应为 1,3-5，且不能超过文档页数') from exc
    return result


def checked_reader(stream):
    reader = PdfReader(stream, strict=True)
    if reader.is_encrypted:
        raise ValueError('不处理加密 PDF')
    root = reader.trailer['/Root']
    if any(key in root for key in ('/AcroForm', '/OpenAction', '/AA')):
        raise ValueError('此 PDF 含表单、签名或自动动作，请先导出普通 PDF')
    if len(reader.pages) > 5000:
        raise ValueError('PDF 超过 5000 页上限')
    for page in reader.pages:
        if '/Annots' in page or '/AA' in page:
            raise ValueError('此 PDF 含注释/链接或页面动作，当前保守模式不处理')
    return reader


def save_pdf(writer, destination, inputs, cancel):
    count = len(writer.pages)
    with SafeOutputWriter(destination, inputs) as output:
        writer.write(output.path)
        def verify(path):
            with path.open('rb') as stream:
                if len(PdfReader(stream, strict=True).pages) != count:
                    raise ValueError('PDF 页面数量校验失败')
        return output.commit(verify, cancel)


def run(request, emit, cancel):
    validate_inputs(request)
    options = request.options
    if not isinstance(options, PdfOptions) or options.mode not in {'merge', 'split', 'extract', 'rotate', 'images'}:
        raise ValueError('PDF 操作无效')
    if options.rotation not in {90, 180, 270}:
        raise ValueError('旋转角度应为 90、180 或 270')
    if options.mode in {'split', 'extract', 'rotate'} and len(request.inputs) != 1:
        raise ValueError('拆分、抽页和旋转每次请选择一个 PDF')
    if len(request.inputs) > 200 or sum(p.stat().st_size for p in request.inputs) > 512 * 1024**2:
        raise ValueError('单次最多 200 个文件，输入总量最多 512 MB')
    results = []
    with ExitStack() as stack:
        writer = PdfWriter()
        for index, source in enumerate(request.inputs, 1):
            check_cancel(cancel)
            if options.mode == 'images':
                with load_photo(source) as image:
                    image.thumbnail((2480, 3508))
                    page = Image.new('RGB', (2480, 3508), 'white')
                    picture = image.convert('RGBA')
                    page.paste(picture, ((2480 - picture.width) // 2, (3508 - picture.height) // 2), picture)
                    buffer = stack.enter_context(BytesIO())
                    page.save(buffer, 'PDF', resolution=300)
                    buffer.seek(0)
                    reader = PdfReader(buffer)
                    page.close()
            else:
                if source.suffix.lower() != '.pdf' or source.stat().st_size > 512 * 1024**2:
                    raise ValueError('请选择 512 MB 以内的 PDF 文件')
                reader = checked_reader(stack.enter_context(source.open('rb')))
            selected = parse_pages(options.pages, len(reader.pages))
            if options.mode == 'split':
                for number in selected:
                    single = PdfWriter()
                    try:
                        check_cancel(cancel)
                        single.add_page(reader.pages[number])
                        output = save_pdf(single, request.output_dir / f'{source.stem[:80]}_第{number + 1}页.pdf', request.inputs, cancel)
                        results.append(success(source, output, f'已拆分第 {number + 1} 页'))
                    except Cancelled:
                        results.append(FileResult(source, None, 'cancelled',
                            f'第 {number + 1} 页起已取消；之前完成的页面保留'))
                        break
                    except MemoryError:
                        raise
                    except Exception as exc:
                        results.append(FileResult(source, None, 'failed',
                            f'第 {number + 1} 页失败：{friendly_error(exc)}'))
                    finally:
                        single.close()
            else:
                numbers = selected if options.mode == 'extract' else range(len(reader.pages))
                for number in numbers:
                    check_cancel(cancel)
                    page = writer.add_page(reader.pages[number])
                    if options.mode == 'rotate' and number in selected:
                        page.rotate(options.rotation)
            emit(Progress(index, len(request.inputs), '正在整理 PDF 页面'))
        if options.mode != 'split':
            output = save_pdf(writer, request.output_dir / '整理结果.pdf', request.inputs, cancel)
            results.append(success(request.inputs[0], output, f'已输出 {len(writer.pages)} 页；原书签不保留'))
        writer.close()
    return tuple(results)
