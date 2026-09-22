from pathlib import Path
import argparse
import os
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def build(mode):
    if os.name != 'nt':
        raise SystemExit('Windows releases must be built on Windows')
    from fetch_ffmpeg import fetch
    from notices import generate
    fetch()
    generate()
    version = os.environ.get('GITHUB_REF_NAME', 'development')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    (ROOT / 'assets/version.json').write_text(json.dumps({'version': version, 'commit': commit}), encoding='utf-8')
    name = 'WanwanTeacherHelper' if mode == 'onefile' else 'WanwanTeacherHelperDebug'
    args = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', '--noupx',
            '--windowed', f'--{mode}', '--name', name, '--icon', str(ROOT / 'assets/icon.ico'),
            '--exclude-module', 'PySide6.QtWebEngineCore', '--exclude-module', 'PySide6.QtWebEngineWidgets',
            '--exclude-module', 'pytest', '--exclude-module', 'ruff',
            '--add-data', f'{ROOT / "licenses"};licenses', '--add-data', f'{ROOT / "assets"};assets',
            '--add-data', f'{ROOT / "vendor/ffmpeg"};vendor/ffmpeg',
            '--hidden-import', 'PIL.PdfImagePlugin', str(ROOT / 'main.py')]
    subprocess.run(args, cwd=ROOT, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['onedir', 'onefile'])
    build(parser.parse_args().mode)
