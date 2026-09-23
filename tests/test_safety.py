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


def test_validation_failure_and_precommit_cancel_cleanup(tmp_path):
    target = tmp_path / 'result.txt'
    with pytest.raises(ValueError):
        with SafeOutputWriter(target) as writer:
            writer.path.write_text('bad')
            writer.commit(lambda _: (_ for _ in ()).throw(ValueError('validation')))
    stop = Event()
    with pytest.raises(Cancelled):
        with SafeOutputWriter(target) as writer:
            writer.path.write_text('complete but cancelled')
            stop.set()
            writer.commit(cancel=stop)
    assert not list(tmp_path.iterdir())


def test_disk_full_during_flush_preserves_original(tmp_path, monkeypatch):
    import errno
    import os
    original = tmp_path / 'source.txt'
    original.write_bytes(b'original')
    def no_space(_):
        raise OSError(errno.ENOSPC, 'No space left on device')
    monkeypatch.setattr(os, 'fsync', no_space)
    with pytest.raises(OSError, match='No space'):
        with SafeOutputWriter(tmp_path / 'output.txt', (original,)) as writer:
            writer.path.write_bytes(b'pending')
            writer.commit()
    assert original.read_bytes() == b'original'
    assert list(tmp_path.iterdir()) == [original]


def test_long_unicode_output_path(tmp_path):
    parent = tmp_path
    for _ in range(8):
        parent /= '幼儿园活动资料与照片整理目录'
    with SafeOutputWriter(parent / '成品.txt') as writer:
        writer.path.write_bytes(b'complete')
        output = writer.commit()
    assert output.read_bytes() == b'complete'
    assert not list(parent.glob('.wanwan-*'))


def test_windows_locked_destination_is_never_overwritten(tmp_path):
    import os
    if os.name != 'nt':
        pytest.skip('Requires Windows mandatory file sharing locks')
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    target = tmp_path / 'locked.txt'
    target.write_bytes(b'original')
    handle = kernel.CreateFileW(str(target), 0x80000000, 0, None, 3, 0, None)
    assert handle != wintypes.HANDLE(-1).value
    try:
        try:
            with SafeOutputWriter(target) as writer:
                writer.path.write_bytes(b'copy')
                result = writer.commit()
            assert result != target and result.read_bytes() == b'copy'
        except PermissionError:
            assert not list(tmp_path.glob('.wanwan-*'))
    finally:
        kernel.CloseHandle(handle)
    assert target.read_bytes() == b'original'
