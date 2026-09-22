from pathlib import Path
from threading import Event
import hashlib
import json
import pytest
from app.core.engine_cache import prepare_engine
from app.core.safe_output import Cancelled


def bundle(tmp_path):
    source = tmp_path / 'bundle'
    (source / 'bin').mkdir(parents=True)
    files = []
    for name in ('ffmpeg.exe', 'ffprobe.exe', 'avcodec.dll'):
        path = source / 'bin' / name
        path.write_bytes(name.encode())
        files.append({'path': f'bin/{name}', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = source / 'manifest.json'
    manifest.write_text(json.dumps({'files': files}))
    return manifest


def test_cache_reuses_verified_files_and_repairs_corruption(tmp_path):
    manifest = bundle(tmp_path)
    cache = tmp_path / 'cache'
    first = prepare_engine(manifest, cache, Event())
    assert first != manifest.parent
    assert (first / 'bin/ffmpeg.exe').read_bytes() == b'ffmpeg.exe'
    assert prepare_engine(manifest, cache, Event()) == first
    (first / 'bin/ffmpeg.exe').write_bytes(b'corrupted')
    assert prepare_engine(manifest, cache, Event()) == first
    assert (first / 'bin/ffmpeg.exe').read_bytes() == b'ffmpeg.exe'
    assert not list(cache.glob('.stage-*'))


@pytest.mark.parametrize('path', ['../ffmpeg.exe', '/ffmpeg.exe', 'bin\\ffmpeg.exe', 'bin/evil.exe'])
def test_manifest_rejects_unsafe_or_unknown_programs(tmp_path, path):
    manifest = bundle(tmp_path)
    data = json.loads(manifest.read_text())
    data['files'][0]['path'] = path
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        prepare_engine(manifest, tmp_path / 'cache', Event())


def test_cancel_and_invalid_bundle_leave_no_usable_cache(tmp_path):
    manifest = bundle(tmp_path)
    stop = Event()
    stop.set()
    with pytest.raises(Cancelled):
        prepare_engine(manifest, tmp_path / 'cache', stop)
    (manifest.parent / 'bin/ffmpeg.exe').write_bytes(b'bad')
    with pytest.raises(ValueError):
        prepare_engine(manifest, tmp_path / 'cache', Event())
    assert not list((tmp_path / 'cache').glob('.stage-*'))


def test_concurrent_processes_publish_one_valid_engine(tmp_path):
    import subprocess
    import sys
    manifest = bundle(tmp_path)
    cache = tmp_path / 'cache'
    script = ('from app.core.engine_cache import prepare_engine; from pathlib import Path; '
              'from threading import Event; import sys; '
              'print(prepare_engine(Path(sys.argv[1]),Path(sys.argv[2]),Event()))')
    processes = [subprocess.Popen([sys.executable, '-c', script, str(manifest), str(cache)],
                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(3)]
    outputs = []
    for process in processes:
        out, err = process.communicate(timeout=15)
        assert process.returncode == 0, err
        outputs.append(out.strip())
    assert len(set(outputs)) == 1
    assert Path(outputs[0]).is_dir()
