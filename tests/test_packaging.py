"""Windows release scripts must parse and refuse an absent signing identity."""
import os
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name != 'nt', reason='Requires Windows PowerShell')
def test_release_scripts_parse_and_signing_fails_closed(tmp_path):
    command = """
    $ErrorActionPreference = 'Stop'
    Get-ChildItem scripts/*.ps1 | ForEach-Object {
        $tokens = $null; $errors = $null
        $null = [System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$errors)
        if ($errors.Count) { throw ($errors | Out-String) }
    }
    """
    subprocess.run(['pwsh', '-NoProfile', '-Command', command], cwd=ROOT, check=True)
    executable = tmp_path / 'unsigned.exe'
    executable.write_bytes(b'unsigned fixture')
    environment = {k: v for k, v in os.environ.items() if not k.startswith('WANWAN_SIGNING_')}
    result = subprocess.run(['pwsh', '-NoProfile', '-File', 'scripts/sign_release.ps1',
                             '-Path', str(executable)], cwd=ROOT, env=environment,
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'expected production certificate thumbprint' in result.stderr
    assert executable.read_bytes() == b'unsigned fixture'
