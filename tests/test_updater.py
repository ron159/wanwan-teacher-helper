import hashlib
import json
import os
import subprocess

import pytest

from app import updater


def release(tag, *, draft=False, complete=True):
    prefix = f'https://github.com/{updater.REPOSITORY}/releases/download/{tag}/'
    names = [f'WanwanTeacherHelper-{tag}-windows-x64.exe', 'SHA256SUMS.txt']
    if not complete:
        names.pop()
    return {'tag_name': tag, 'draft': draft,
            'assets': [{'name': name, 'browser_download_url': prefix + name} for name in names]}


def test_find_update_includes_preview_and_chooses_newest(monkeypatch):
    releases = [release('v0.2.0-preview.2'), release('v0.2.0-preview.3', draft=True),
                release('v0.2.0'), release('v0.3.0-preview.1', complete=False)]
    monkeypatch.setattr(updater, '_read_url', lambda _: json.dumps(releases).encode())
    result = updater.find_update('v0.2.0-preview.1')
    assert result['version'] == 'v0.2.0'
    assert updater.find_update('v0.2.0') is None
    assert updater.find_update('development') is None


def test_download_update_verifies_checksum(monkeypatch, tmp_path):
    body = b'new executable'
    name = 'WanwanTeacherHelper-v0.2.0-windows-x64.exe'
    expected = hashlib.sha256(body).hexdigest()
    update = {'name': name, 'url': 'https://example.test/file',
              'checksums_url': 'https://example.test/checksums'}
    monkeypatch.setattr(updater, '_read_url', lambda _: f'{expected}  {name}\n'.encode())
    folders = iter([tmp_path / 'first', tmp_path / 'second'])

    def make_folder(**_):
        folder = next(folders)
        folder.mkdir()
        return str(folder)

    monkeypatch.setattr(updater.tempfile, 'mkdtemp', make_folder)

    class Response:
        headers = {'Content-Length': str(len(body))}

        def __enter__(self):
            self.remaining = body
            return self

        def __exit__(self, *_):
            pass

        def read(self, _):
            result, self.remaining = self.remaining, b''
            return result

    monkeypatch.setattr(updater, 'urlopen', lambda *_args, **_kwargs: Response())
    progress = []
    path, digest = updater.download_update(update, lambda done, total: progress.append((done, total)))
    assert path.read_bytes() == body
    assert digest == expected
    assert progress == [(len(body), len(body))]
    path.unlink()
    with pytest.raises(ValueError, match='校验失败'):
        monkeypatch.setattr(updater, '_read_url', lambda _: f'{"0" * 64}  {name}\n'.encode())
        updater.download_update(update)
    assert not (tmp_path / 'second').exists()


def test_rejects_release_asset_from_other_address(monkeypatch):
    item = release('v0.2.0')
    item['assets'][0]['browser_download_url'] = 'https://example.test/other.exe'
    monkeypatch.setattr(updater, '_read_url', lambda _: json.dumps([item]).encode())
    with pytest.raises(ValueError, match='地址'):
        updater.find_update('v0.1.0')


@pytest.mark.skipif(os.name != 'nt', reason='Requires Windows PowerShell')
def test_update_helper_parses_in_powershell(tmp_path):
    script = tmp_path / 'replace.ps1'
    script.write_text(updater.HELPER_SCRIPT, encoding='utf-8-sig')
    command = f"""
    $tokens = $null; $errors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$tokens, [ref]$errors)
    if ($errors.Count) {{ throw ($errors | Out-String) }}
    """
    subprocess.run(['powershell.exe', '-NoProfile', '-Command', command], check=True)
