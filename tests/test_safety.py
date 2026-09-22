from pathlib import Path
from threading import Event
import pytest
from app.core.safe_output import SafeOutputWriter, Cancelled, check_cancel, safe_name


def test_output_never_overwrites_and_cleans(tmp_path):
    target = tmp_path / '照片.jpg'
    target.write_bytes(b'original')
    with SafeOutputWriter(target) as writer:
        writer.path.write_bytes(b'copy')
        result = writer.commit()
    assert target.read_bytes() == b'original'
    assert result != target and result.read_bytes() == b'copy'
    assert len(list(tmp_path.iterdir())) == 2


def test_failure_does_not_leave_partial_file(tmp_path):
    with pytest.raises(ValueError):
        with SafeOutputWriter(tmp_path / 'a.txt') as writer:
            writer.path.write_bytes(b'partial')
            raise ValueError('bad')
    assert not list(tmp_path.iterdir())


def test_input_destination_rejected(tmp_path):
    source = tmp_path / 'input.txt'
    source.write_text('keep')
    with pytest.raises(ValueError):
        SafeOutputWriter(source, sources=(source,))


def test_cancel_and_unsafe_names():
    event = Event()
    event.set()
    with pytest.raises(Cancelled):
        check_cancel(event)
    for name in ['../x', 'CON', 'a/b', '', 'a:b', 'a.']:
        with pytest.raises(ValueError):
            safe_name(name)
    assert safe_name('春游照片') == '春游照片'
