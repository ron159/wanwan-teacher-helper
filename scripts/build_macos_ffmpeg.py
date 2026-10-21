"""Build native LGPL FFmpeg binaries using only Apple's system libraries."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def build_engine():
    if sys.platform != 'darwin':
        raise SystemExit('macOS media engines must be built on macOS')
    lock = json.loads((ROOT / 'packaging/ffmpeg-macos-lock.json').read_text())
    destination = ROOT / 'vendor' / f'ffmpeg-macos-{platform.machine()}'
    manifest = destination / 'manifest.json'
    if manifest.exists():
        data = json.loads(manifest.read_text())
        if (data['sha256'] == lock['sha256'] and data['configure'] == lock['configure']
                and all((destination / item['path']).is_file() and hashlib.sha256(
                    (destination / item['path']).read_bytes()).hexdigest() == item['sha256']
                    for item in data['files'])):
            return destination
        raise ValueError('Existing macOS engine failed verification; inspect it before rebuilding')
    work = ROOT / 'build' / f'ffmpeg-macos-{platform.machine()}'
    work.mkdir(parents=True, exist_ok=True)
    archive = work / f'ffmpeg-{lock["version"]}.tar.xz'
    if not archive.exists():
        urllib.request.urlretrieve(lock['url'], archive)
    with archive.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != lock['sha256']:
            raise ValueError('FFmpeg source archive hash mismatch')
    source = work / f'ffmpeg-{lock["version"]}'
    if not source.exists():
        with tarfile.open(archive) as bundle:
            bundle.extractall(work, filter='data')
    environment = {**os.environ, 'MACOSX_DEPLOYMENT_TARGET': '13.0'}
    subprocess.run(['./configure', *lock['configure']], cwd=source, env=environment, check=True)
    subprocess.run(['make', f'-j{min(os.cpu_count() or 2, 8)}', 'ffmpeg', 'ffprobe'],
                   cwd=source, env=environment, check=True)
    (destination / 'bin').mkdir(parents=True, exist_ok=True)
    for name in ('ffmpeg', 'ffprobe'):
        shutil.copy2(source / name, destination / 'bin' / name)
    for name in ('LICENSE.md', 'COPYING.LGPLv2.1'):
        shutil.copy2(source / name, destination / name)
    records = [{'path': path.relative_to(destination).as_posix(),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
               for path in sorted(destination.rglob('*')) if path.is_file()]
    manifest.write_text(json.dumps({**lock, 'architecture': platform.machine(), 'files': records},
                                   indent=2), encoding='utf-8')
    return destination


if __name__ == '__main__':
    print(build_engine())
