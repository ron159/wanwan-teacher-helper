"""Build-time only download. Runtime has no download or network dependency."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import shutil
import stat
import tempfile
import urllib.request
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def fetch():
    lock = json.loads((ROOT / 'packaging/ffmpeg-lock.json').read_text())
    destination = ROOT / 'vendor/ffmpeg'
    if (destination / 'manifest.json').exists():
        manifest = json.loads((destination / 'manifest.json').read_text())
        if manifest['archive_sha256'] == lock['sha256'] and all(
            (destination / f['path']).is_file() and hashlib.sha256(
                (destination / f['path']).read_bytes()).hexdigest() == f['sha256']
            for f in manifest['files']):
            return
        raise ValueError('Existing vendor directory failed verification; remove it explicitly before rebuilding')
    destination.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        staging = Path(temp)
        archive = staging / 'download.zip'
        urllib.request.urlretrieve(lock['url'], archive)
        with archive.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == lock['sha256'], 'Archive hash mismatch'
        unpack = staging / 'ffmpeg'
        unpack.mkdir()
        with ZipFile(archive) as zip_file:
            names = set()
            total = 0
            for info in zip_file.infolist():
                path = PurePosixPath(info.filename)
                total += info.file_size
                if (path.is_absolute() or '..' in path.parts or '\\' in info.filename
                        or ':' in info.filename or stat.S_ISLNK(info.external_attr >> 16)
                        or info.filename in names or total > 1024**3):
                    raise ValueError('Unsafe vendor archive')
                names.add(info.filename)
                if len(path.parts) < 2 or info.is_dir():
                    continue
                relative = Path(*path.parts[1:])
                if relative.suffix.lower() == '.exe' and relative.name not in {'ffmpeg.exe', 'ffprobe.exe', 'ffplay.exe'}:
                    raise ValueError('Unknown executable in vendor archive')
                target = unpack / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with zip_file.open(info) as src, target.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
        for name in ('ffmpeg.exe', 'ffprobe.exe'):
            if not (unpack / 'bin' / name).is_file():
                raise ValueError('Missing required engine')
        files = []
        for path in sorted(unpack.rglob('*')):
            if path.is_file():
                files.append({'path': path.relative_to(unpack).as_posix(),
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        (unpack / 'manifest.json').write_text(json.dumps({**lock, 'archive_sha256': lock['sha256'],
            'files': files}, indent=2), encoding='utf-8')
        unpack.rename(destination)
    print(f'Verified {len(files)} FFmpeg files')


if __name__ == '__main__':
    fetch()
