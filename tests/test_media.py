import subprocess
from types import SimpleNamespace
from threading import Event
from app.tools.media import engines, run, probe, execute
from app.core.contracts import JobRequest, MediaOptions
from app.core.safe_output import Cancelled
import pytest
from app.tools import media


def test_frozen_macos_uses_only_bundled_native_engines(tmp_path, monkeypatch):
    monkeypatch.setattr(media, 'sys', SimpleNamespace(frozen=True, platform='darwin'))
    monkeypatch.setattr(media, 'resource', lambda name: tmp_path / name)
    programs = [tmp_path / f'vendor/ffmpeg/bin/{name}' for name in ('ffmpeg', 'ffprobe')]
    for program in programs:
        program.parent.mkdir(parents=True, exist_ok=True)
        program.write_bytes(b'native engine fixture')
        program.chmod(0o755)
    assert engines() == tuple(str(path) for path in programs)
    programs[0].unlink()
    with pytest.raises(ValueError, match='影音引擎缺失'):
        engines()


def test_real_audio_video_and_cancel(tmp_path):
    ffmpeg, _ = engines()
    source = tmp_path / '活动.avi'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=12',
                    '-f', 'lavfi', '-i', 'sine=frequency=440', '-t', '1', '-c:v', 'rawvideo',
                    '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', str(source)], check=True)
    for mode in ('video', 'audio', 'wav'):
        result = run(JobRequest('media', (source,), tmp_path / 'out', MediaOptions(mode)),
                     lambda p: None, Event())
        assert result[0].status == 'success', result[0].message
        assert float(probe(result[0].output, Event())['format']['duration']) > .8
    event = Event()
    event.set()
    with pytest.raises(Cancelled):
        execute([ffmpeg, '-version'], event)
