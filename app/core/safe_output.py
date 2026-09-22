"""Validated temporary files with atomic, no-replace publication."""
from pathlib import Path
from threading import Event
import os
import re
import tempfile


class Cancelled(Exception):
    pass


def check_cancel(cancel: Event):
    if cancel.is_set():
        raise Cancelled('已取消，未完成的临时文件已清理')


def safe_name(name: str) -> str:
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
                *(f'LPT{i}' for i in range(1, 10))}
    if (not name or len(name) > 120 or name[-1:] in {' ', '.'}
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or name.split('.')[0].upper() in reserved or name in {'.', '..'}):
        raise ValueError('名称不能含路径、特殊字符、保留名或末尾空格/句点（最多 120 字）')
    return name


class SafeOutputWriter:
    def __init__(self, destination: Path, sources: tuple[Path, ...] = ()):
        self.destination = Path(destination)
        safe_name(self.destination.name)
        if self.destination.resolve() in {p.resolve() for p in sources}:
            raise ValueError('输出不得与原文件相同')
        self.path: Path | None = None

    def __enter__(self):
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix='.wanwan-', suffix=self.destination.suffix,
                                    dir=self.destination.parent)
        os.close(fd)
        self.path = Path(path)
        return self

    def commit(self, validate=None, cancel: Event | None = None) -> Path:
        if validate:
            validate(self.path)
        if cancel:
            check_cancel(cancel)
        # Windows FlushFileBuffers requires a writable handle.
        with self.path.open('r+b') as stream:
            os.fsync(stream.fileno())
        for number in range(10000):
            target = self.destination if number == 0 else self.destination.with_name(
                f'{self.destination.stem} ({number}){self.destination.suffix}')
            try:
                if os.name == 'nt':
                    # Windows rename refuses an existing target, including on FAT/exFAT.
                    os.rename(self.path, target)
                else:
                    os.link(self.path, target)
                    self.path.unlink()
                return target
            except FileExistsError:
                continue
        raise FileExistsError('同名文件过多，请选择新输出目录')

    def __exit__(self, *_):
        if self.path:
            self.path.unlink(missing_ok=True)
