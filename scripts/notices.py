"""Build machine's exact installed metadata and license texts, no invented licenses."""
from importlib.metadata import distributions
from pathlib import Path
import json
import shutil
import subprocess
import os

ROOT = Path(__file__).resolve().parents[1]


def generate(engine=None):
    engine = engine or ROOT / 'vendor/ffmpeg'
    target = ROOT / 'licenses/generated'
    target.mkdir(parents=True, exist_ok=True)
    components = []
    for dist in sorted(distributions(), key=lambda d: d.metadata['Name'].lower()):
        name = dist.metadata['Name']
        metadata = dist.metadata
        license_id = metadata.get('License-Expression') or metadata.get('License') or 'See bundled texts'
        texts = []
        for file in dist.files or []:
            if any(key in file.name.lower() for key in ('license', 'copying', 'notice')) and (
                    '.dist-info' in str(file) or name.lower() in {'pyside6', 'pyside6_essentials', 'pyside6_addons'}):
                original = Path(dist.locate_file(file))
                if original.is_file() and original.stat().st_size < 2_000_000:
                    destination = target / name / str(file).replace('../', '')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(original, destination)
                    texts.append(destination.relative_to(ROOT / 'licenses').as_posix())
        components.append({'type': 'library', 'name': name, 'version': dist.version,
                           'purl': f'pkg:pypi/{name.lower()}@{dist.version}',
                           'properties': [{'name': 'license-metadata', 'value': license_id},
                                          {'name': 'license-files', 'value': json.dumps(texts)}]})
    manifest = engine / 'manifest.json'
    if manifest.exists():
        shutil.copyfile(manifest, ROOT / 'licenses/ffmpeg-manifest.json')
        executable = engine / 'bin' / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
        if executable.exists():
            for flag, filename in [('-version', 'ffmpeg-build.txt'), ('-L', 'ffmpeg-license.txt')]:
                result = subprocess.run([str(executable), flag], capture_output=True, check=True)
                (ROOT / 'licenses' / filename).write_bytes(result.stdout + result.stderr)
        for name in ('LICENSE.md', 'COPYING.LGPLv2.1'):
            if (engine / name).exists():
                (target / 'FFmpeg').mkdir(exist_ok=True)
                shutil.copy2(engine / name, target / 'FFmpeg' / name)
        lock = json.loads(manifest.read_text())
        components.append({'type': 'application', 'name': 'FFmpeg', 'version': lock['version'],
                           'hashes': [{'alg': 'SHA-256', 'content': lock['sha256']}],
                           'externalReferences': [{'type': 'distribution', 'url': lock['url']}]})
    (ROOT / 'licenses/sbom.cdx.json').write_text(json.dumps({
        'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1,
        'components': components}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    generate()
