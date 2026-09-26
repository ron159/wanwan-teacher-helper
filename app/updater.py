"""GitHub Release discovery and verified replacement of the portable Windows EXE."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

from app.resources import resource


REPOSITORY = 'ron159/wanwan-teacher-helper'
RELEASES_API = f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=100'
VERSION_RE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)(?:-preview\.(\d+))?$')
CHECKSUM_RE = re.compile(r'^([0-9a-fA-F]{64})  (\S+)$')


def version_key(version):
    match = VERSION_RE.fullmatch(version)
    if not match:
        return None
    major, minor, patch, preview = match.groups()
    return (int(major), int(minor), int(patch), 1 if preview is None else 0,
            0 if preview is None else int(preview))


def current_version():
    try:
        return json.loads(resource('assets/version.json').read_text(encoding='utf-8'))['version']
    except (FileNotFoundError, KeyError, ValueError):
        return None


def _read_url(url):
    request = Request(url, headers={'Accept': 'application/vnd.github+json',
                                    'User-Agent': 'WanwanTeacherHelper-Updater'})
    with urlopen(request, timeout=20) as response:
        return response.read()


def find_update(installed_version):
    installed = version_key(installed_version)
    if installed is None:
        return None
    releases = json.loads(_read_url(RELEASES_API))
    candidates = []
    for release in releases:
        tag = release.get('tag_name', '')
        key = version_key(tag)
        if release.get('draft') or key is None or key <= installed:
            continue
        filename = f'WanwanTeacherHelper-{tag}-windows-x64.exe'
        assets = {asset['name']: asset for asset in release.get('assets', [])}
        if filename in assets and 'SHA256SUMS.txt' in assets:
            candidates.append((key, tag, assets[filename], assets['SHA256SUMS.txt']))
    if not candidates:
        return None
    _, tag, executable, checksums = max(candidates, key=lambda item: item[0])
    prefix = f'https://github.com/{REPOSITORY}/releases/download/{tag}/'
    if executable.get('browser_download_url') != prefix + executable['name']:
        raise ValueError('发行文件地址与版本不匹配')
    if checksums.get('browser_download_url') != prefix + 'SHA256SUMS.txt':
        raise ValueError('校验文件地址与版本不匹配')
    return {'version': tag, 'name': executable['name'], 'url': executable['browser_download_url'],
            'checksums_url': checksums['browser_download_url'],
            'page': f'https://github.com/{REPOSITORY}/releases/tag/{tag}'}


def download_update(update, progress=None):
    checksums = _read_url(update['checksums_url']).decode('utf-8-sig')
    expected = None
    for line in checksums.splitlines():
        match = CHECKSUM_RE.fullmatch(line.strip())
        if match and match.group(2) == update['name']:
            expected = match.group(1).lower()
            break
    if expected is None:
        raise ValueError('发行校验清单缺少程序文件')
    folder = Path(tempfile.mkdtemp(prefix='wanwan-update-'))
    destination = folder / update['name']
    digest = hashlib.sha256()
    request = Request(update['url'], headers={'User-Agent': 'WanwanTeacherHelper-Updater'})
    try:
        with urlopen(request, timeout=30) as response, destination.open('wb') as output:
            total = int(response.headers.get('Content-Length', '0'))
            done = 0
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if digest.hexdigest() != expected:
            raise ValueError('下载文件 SHA-256 校验失败')
        return destination, expected
    except Exception:
        destination.unlink(missing_ok=True)
        folder.rmdir()
        raise


HELPER_SCRIPT = r'''param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Target,
    [Parameter(Mandatory=$true)][int]$ParentPid,
    [Parameter(Mandatory=$true)][string]$ExpectedHash
)
$ErrorActionPreference = 'Stop'
$backup = "$Target.previous-$([guid]::NewGuid().ToString('N'))"
$replacement = "$Target.update"
try {
    Wait-Process -Id $ParentPid -Timeout 120 -ErrorAction SilentlyContinue
    if (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {
        throw '旧版程序未能退出'
    }
    if ((Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash.ToLower() -ne $ExpectedHash) {
        throw '下载文件 SHA-256 校验失败'
    }
    Copy-Item -LiteralPath $Source -Destination $replacement -Force
    if ((Get-FileHash -LiteralPath $replacement -Algorithm SHA256).Hash.ToLower() -ne $ExpectedHash) {
        throw '替换文件 SHA-256 校验失败'
    }
    Move-Item -LiteralPath $Target -Destination $backup -Force
    try {
        Move-Item -LiteralPath $replacement -Destination $Target -Force
        Start-Process -FilePath $Target -WorkingDirectory (Split-Path -Parent $Target)
        Remove-Item -LiteralPath $backup -Force
    } catch {
        if (Test-Path -LiteralPath $backup) {
            Remove-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
            Move-Item -LiteralPath $backup -Destination $Target -Force
        }
        throw
    }
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show("自动更新失败：$($_.Exception.Message)", '丸丸小帮手') | Out-Null
} finally {
    Remove-Item -LiteralPath $replacement -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Source -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Split-Path -Parent $PSCommandPath) -Force -ErrorAction SilentlyContinue
}
'''


def launch_replacement(downloaded, expected_hash):
    if os.name != 'nt' or not getattr(sys, 'frozen', False):
        raise RuntimeError('自动替换仅支持 Windows 单文件发行版')
    target = Path(sys.executable).resolve()
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.wanwan-write-check-',
                                     delete=True):
        pass
    script = downloaded.parent / 'replace.ps1'
    script.write_text(HELPER_SCRIPT, encoding='utf-8-sig')
    # PowerShell passes this on to the restarted onefile EXE after the old bundle is removed.
    subprocess.Popen(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                      '-WindowStyle', 'Hidden', '-File', str(script), '-Source', str(downloaded),
                      '-Target', str(target), '-ParentPid', str(os.getpid()),
                      '-ExpectedHash', expected_hash],
                     env={**os.environ, 'PYINSTALLER_RESET_ENVIRONMENT': '1'}, close_fds=True,
                     creationflags=subprocess.CREATE_NO_WINDOW)
