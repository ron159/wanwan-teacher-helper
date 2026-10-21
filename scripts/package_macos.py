"""Collect the tested macOS app, licenses, sources, and checksums for Release."""
import hashlib
import json
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import tomllib
from macholib.MachO import MachO
from macholib.mach_o import LC_BUILD_VERSION, LC_VERSION_MIN_MACOSX

ROOT = Path(__file__).resolve().parents[1]


def verify_bundle():
    bundle = (ROOT / 'dist/WanwanTeacherHelper.app').resolve()
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(bundle)], check=True)
    executable = bundle / 'Contents/MacOS/WanwanTeacherHelper'
    architecture = subprocess.check_output(['lipo', '-archs', str(executable)], text=True).strip()
    if architecture != 'arm64':
        raise ValueError(f'Expected an Apple Silicon application, got {architecture}')
    metadata = plistlib.loads((bundle / 'Contents/Info.plist').read_bytes())
    if metadata['LSMinimumSystemVersion'] != '15.0':
        raise ValueError('Unexpected minimum macOS version')
    binaries = {}
    for item in bundle.rglob('*'):
        if not item.is_file():
            continue
        path = item.resolve()
        if not path.is_relative_to(bundle):
            raise ValueError(f'Application links outside its bundle: {item}')
        if path in binaries:
            continue
        with path.open('rb') as stream:
            if stream.read(4) not in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe'):
                continue
        minimum = (0, 0, 0)
        for header in MachO(str(path)).headers:
            for load, command, _ in header.commands:
                if load.cmd in (LC_BUILD_VERSION, LC_VERSION_MIN_MACOSX):
                    value = command.minos if load.cmd == LC_BUILD_VERSION else command.version
                    minimum = max(minimum, (value >> 16, (value >> 8) & 255, value & 255))
        if minimum > (15, 0, 0):
            raise ValueError(f'Bundled binary requires macOS {minimum}: {path}')
        binaries[path] = minimum
    libraries = subprocess.check_output(['otool', '-L', *map(str, binaries)], text=True)
    for line in libraries.splitlines():
        if line.startswith('\t/') and not line.lstrip().startswith(('/usr/lib/', '/System/Library/')):
            raise ValueError(f'Application depends on a non-system external library: {line}')
    return {'architecture': architecture, 'minimum_macos': '15.0', 'macho_files': len(binaries),
            'codesign_verified': True, 'external_non_system_libraries': []}


def package():
    verification = verify_bundle()
    version = f'v{tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]}'
    architecture = platform.machine()
    target = ROOT / 'artifacts/release-macos'
    target.mkdir(parents=True, exist_ok=True)
    archive = f'WanwanTeacherHelper-{version}-macos-{architecture}.zip'
    shutil.copy2(ROOT / 'dist' / archive, target / archive)
    for source, name in (
        ('artifacts/macos-smoke/self-test.json', 'macos-self-test.json'),
        ('artifacts/macos-smoke/ui.png', 'macos-ui.png'),
        ('artifacts/macos-startup/startup-probe.json', 'macos-startup-probe.json'),
        ('licenses/ffmpeg-build.txt', 'macos-ffmpeg-build.txt'),
        ('licenses/sbom.cdx.json', 'macos-sbom.cdx.json'),
    ):
        shutil.copy2(ROOT / source, target / name)
    lock = json.loads((ROOT / 'packaging/ffmpeg-macos-lock.json').read_text())
    source = ROOT / 'build' / f'ffmpeg-macos-{architecture}' / f'ffmpeg-{lock["version"]}.tar.xz'
    shutil.copy2(source, target / source.name)
    shutil.make_archive(str(target / 'third-party-licenses-macos'), 'zip', ROOT / 'licenses')
    (target / 'macos-signature.json').write_text(json.dumps({
        'version': version, 'architecture': architecture, 'status': 'AdHocNotNotarized',
        'minimum_macos': '15.0', 'developer_id_signed': False, 'notarized': False,
    }, indent=2), encoding='utf-8')
    (target / 'macos-bundle-verification.json').write_text(
        json.dumps(verification, indent=2), encoding='utf-8')
    records = []
    for path in sorted(target.iterdir()):
        if path.is_file() and path.name != 'SHA256SUMS-macos.txt':
            with path.open('rb') as stream:
                records.append(f'{hashlib.file_digest(stream, "sha256").hexdigest()}  {path.name}')
    (target / 'SHA256SUMS-macos.txt').write_text('\n'.join(records) + '\n', encoding='utf-8')
    print(target)


if __name__ == '__main__':
    package()
