from pathlib import Path
from app.core.contracts import FileResult, JobRequest, Progress
from app.core.safe_output import Cancelled, check_cancel


def validate_inputs(request: JobRequest, allow_empty=False):
    if not request.inputs and not allow_empty:
        raise ValueError('请先添加文件')
    if len(request.inputs) > 10000:
        raise ValueError('单次最多处理 10000 个文件')
    for path in request.inputs:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'不是普通文件或为符号链接：{path.name}')
    if request.output_dir.exists() and not request.output_dir.is_dir():
        raise ValueError('输出位置不是目录')


def run_files(request, processor, emit, cancel):
    results = []
    for index, source in enumerate(request.inputs, 1):
        try:
            check_cancel(cancel)
            result = processor(source, request, index, cancel)
        except Cancelled as exc:
            results.extend(FileResult(p, None, 'cancelled', str(exc))
                           for p in request.inputs[index - 1:])
            break
        except MemoryError:
            raise
        except Exception as exc:
            result = FileResult(source, None, 'failed', friendly_error(exc))
        results.append(result)
        emit(Progress(index, len(request.inputs), result.message))
    return tuple(results)


def friendly_error(exc):
    if isinstance(exc, PermissionError):
        return '文件被占用或无权限，请关闭占用程序并检查输出目录权限'
    if isinstance(exc, OSError) and exc.errno == 28:
        return '磁盘空间不足，请更换输出位置'
    # Do not leak full source paths, document bodies or subprocess stderr to logs.
    if isinstance(exc, ValueError):
        return str(exc)
    return f'文件无法处理（{type(exc).__name__}），请检查格式和文件完整性'


def success(source: Path, output: Path, message: str, details=None):
    return FileResult(source, output, 'success', message,
                      source.stat().st_size if source.is_file() else 0,
                      output.stat().st_size, details or {})
