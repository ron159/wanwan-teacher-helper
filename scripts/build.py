from pathlib import Path
import argparse
import os
import json
import platform
import plistlib
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def build(mode):
    macos = mode == 'macos'
    if macos and sys.platform != 'darwin':
        raise SystemExit('macOS applications must be built on macOS')
    if not macos and os.name != 'nt':
        raise SystemExit('Windows releases must be built on Windows')
    from notices import generate
    if macos:
        from build_macos_ffmpeg import build_engine
        engine = build_engine()
    else:
        from fetch_ffmpeg import fetch
        fetch()
        engine = ROOT / 'vendor/ffmpeg'
    generate(engine)
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    version = os.environ.get('GITHUB_REF_NAME', f'v{project["project"]["version"]}')
    if macos and os.environ.get('GITHUB_REF_TYPE') != 'tag':
        version = f'v{project["project"]["version"]}'
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    (ROOT / 'assets/version.json').write_text(json.dumps({'version': version, 'commit': commit}), encoding='utf-8')
    name = 'WanwanTeacherHelper' if macos or mode == 'onefile' else 'WanwanTeacherHelperDebug'
    args = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', '--noupx',
            '--windowed', '--onedir' if macos else f'--{mode}', '--name', name,
            '--icon', str(ROOT / ('assets/icon.png' if macos else 'assets/icon.ico')),
            '--exclude-module', 'PySide6.QtWebEngineCore', '--exclude-module', 'PySide6.QtWebEngineWidgets',
            '--exclude-module', 'pytest', '--exclude-module', 'ruff',
            '--add-data', f'{ROOT / "licenses"}{os.pathsep}licenses',
            '--add-data', f'{ROOT / "assets"}{os.pathsep}assets',
            '--hidden-import', 'PIL.PdfImagePlugin']
    if macos:
        args += ['--target-architecture', platform.machine(), '--osx-bundle-identifier',
                 'com.ron159.wanwan-teacher-helper']
        for program in ('ffmpeg', 'ffprobe'):
            args += ['--add-binary', f'{engine / "bin" / program}:vendor/ffmpeg/bin']
    else:
        args += ['--add-data', f'{engine}{os.pathsep}vendor/ffmpeg']
    args.append(str(ROOT / 'main.py'))
    environment = {**os.environ, 'PYINSTALLER_CONFIG_DIR': str(ROOT / 'build/pyinstaller-cache')}
    subprocess.run(args, cwd=ROOT, env=environment, check=True)
    if macos:
        bundle = ROOT / 'dist' / f'{name}.app'
        info = bundle / 'Contents/Info.plist'
        metadata = plistlib.loads(info.read_bytes())
        metadata.update(CFBundleDisplayName='丸丸小帮手', CFBundleName='丸丸小帮手',
                        CFBundleShortVersionString=project['project']['version'],
                        CFBundleVersion=project['project']['version'], LSMinimumSystemVersion='15.0')
        info.write_bytes(plistlib.dumps(metadata))
        subprocess.run(['codesign', '--force', '--sign', '-', str(bundle)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(bundle)], check=True)
        archive = ROOT / 'dist' / f'{name}-{version}-macos-{platform.machine()}.zip'
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
                        str(bundle), str(archive)], check=True)
        print(f'macOS application: {bundle}\nArchive: {archive}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['onedir', 'onefile', 'macos'])
    build(parser.parse_args().mode)
