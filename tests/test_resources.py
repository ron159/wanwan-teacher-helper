import os
from types import SimpleNamespace

import pytest

from app import resources


@pytest.mark.skipif(os.name == 'nt', reason='macOS bundle uses POSIX symlinks')
def test_macos_resources_accept_bundle_links_and_reject_external_links(tmp_path, monkeypatch):
    contents = tmp_path / 'Helper.app/Contents'
    frameworks = contents / 'Frameworks'
    assets = contents / 'Resources/assets'
    frameworks.mkdir(parents=True)
    assets.mkdir(parents=True)
    icon = assets / 'icon.png'
    icon.write_bytes(b'bundled icon')
    link = frameworks / 'assets'
    link.symlink_to('../Resources/assets', target_is_directory=True)
    monkeypatch.setattr(resources, 'sys', SimpleNamespace(
        frozen=True, platform='darwin', _MEIPASS=str(frameworks)))
    assert resources.resource('assets/icon.png') == icon
    link.unlink()
    outside = tmp_path / 'external'
    outside.mkdir()
    (outside / 'icon.png').write_bytes(b'external icon')
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(FileNotFoundError):
        resources.resource('assets/icon.png')
    with pytest.raises(ValueError):
        resources.resource('../Resources/assets/icon.png')
