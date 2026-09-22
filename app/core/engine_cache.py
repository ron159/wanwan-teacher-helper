"""Content-addressed, locked engine cache. Hashes detect corruption, not hostile users."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from threading import Event
import time
from app.core.safe_output import check_cancel, safe_name


def manifest_files(manifest):
    if manifest.stat().st_size > 2 * 1024**2:
        raise ValueError('引擎清单过大')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    records = data.get('files', [])
    if not records or len(records) > 2000:
        raise ValueError('引擎清单为空或成员过多')
    seen = set()
    for record in records:
        name, digest = record['path'], record['sha256']
        path = PurePosixPath(name)
        if (path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name
                or path.as_posix() != name or name.casefold() in seen
                or not re.fullmatch('[0-9a-f]{64}', digest)):
            raise ValueError('引擎清单含非法路径、重复成员或无效哈希')
        for part in path.parts:
            safe_name(part)
        if path.suffix.lower() in {'.exe', '.com', '.bat', '.cmd', '.ps1', '.msi', '.scr'} and name not in {
                'bin/ffmpeg.exe', 'bin/ffprobe.exe', 'bin/ffplay.exe'}:
            raise ValueError('引擎清单含未知可执行文件')
        seen.add(name.casefold())
    if not {'bin/ffmpeg.exe', 'bin/ffprobe.exe'} <= seen:
        raise ValueError('引擎清单缺少 ffmpeg / ffprobe')
    return records


def digest_file(path, cancel):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024**2):
            check_cancel(cancel)
            digest.update(chunk)
    return digest.hexdigest()


def contained_file(base, relative):
    path = base / relative
    current = path
    while current != base:
        if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
            raise ValueError('引擎目录含符号链接或目录联接')
        current = current.parent
    if not path.resolve().is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError('引擎文件缺失或路径越界')
    return path


def verify(base, records, cancel):
    expected = {r['path'] for r in records}
    actual = set()
    for path in base.rglob('*'):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('引擎目录含链接')
        if path.is_file():
            actual.add(path.relative_to(base).as_posix())
    if actual != expected:
        raise ValueError('引擎目录含缺失或未知文件')
    for record in records:
        check_cancel(cancel)
        path = contained_file(base, record['path'])
        if digest_file(path, cancel) != record['sha256']:
            raise ValueError('引擎文件哈希不一致')


@contextmanager
def process_lock(path, cancel):
    if path.is_symlink():
        raise ValueError('引擎锁文件不能为链接')
    with path.open('a+b') as stream:
        if path.stat().st_size == 0:
            stream.write(b'0')
            stream.flush()
        deadline = time.monotonic() + 120
        while True:
            check_cancel(cancel)
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, PermissionError, OSError):
                if time.monotonic() > deadline:
                    raise ValueError('另一实例正在准备引擎，请稍后重试')
                cancel.wait(.1)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def prepare_engine(manifest: Path, cache: Path, cancel: Event) -> Path:
    check_cancel(cancel)
    records = manifest_files(manifest)
    identity = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
    if cache.is_symlink() or (hasattr(cache, 'is_junction') and cache.is_junction()):
        raise ValueError('引擎缓存根目录不能为链接')
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache = cache.resolve()
    target = cache / identity
    with process_lock(cache / f'{identity}.lock', cancel):
        if target.is_symlink() or (hasattr(target, 'is_junction') and target.is_junction()):
            raise ValueError('引擎缓存不能为链接')
        if target.exists():
            try:
                verify(target, records, cancel)
                return target
            except ValueError:
                # Only this application's exact content-addressed cache is replaceable.
                shutil.rmtree(target)
        with tempfile.TemporaryDirectory(prefix='.stage-', dir=cache) as temporary:
            staging = Path(temporary) / 'engine'
            staging.mkdir()
            total = 0
            for record in records:
                check_cancel(cancel)
                source = contained_file(manifest.parent, record['path'])
                total += source.stat().st_size
                if source.stat().st_size > 512 * 1024**2 or total > 1024**3:
                    raise ValueError('引擎文件容量超过上限')
                destination = staging / record['path']
                destination.parent.mkdir(parents=True, exist_ok=True)
                with source.open('rb') as src, destination.open('xb') as dst:
                    while chunk := src.read(1024**2):
                        check_cancel(cancel)
                        dst.write(chunk)
                    dst.flush()
                    os.fsync(dst.fileno())
            verify(staging, records, cancel)
            check_cancel(cancel)
            staging.rename(target)
        return target
