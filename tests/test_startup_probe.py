import os
from pathlib import Path
import subprocess
import sys
import json
import pytest


@pytest.mark.parametrize('blocked', [False, True])
def test_probe_checks_default_destination_and_exits_on_failure(tmp_path, blocked):
    documents = tmp_path / 'Documents'
    if blocked:
        documents.write_text('not a directory')
    script = '''
from pathlib import Path
import sys
from PySide6.QtCore import QStandardPaths
from app.startup_probe import run_startup_probe
QStandardPaths.writableLocation = lambda _: sys.argv[1]
sys.exit(run_startup_probe(Path(sys.argv[2])))
'''
    report = tmp_path / 'report'
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    result = subprocess.run([sys.executable, '-c', script, str(documents), str(report)],
                            cwd=Path(__file__).resolve().parents[1], env=environment,
                            capture_output=True, timeout=30)
    assert result.returncode == (1 if blocked else 0), result.stderr
    if blocked:
        assert (report / 'startup-failure.txt').is_file()
    else:
        data = json.loads((report / 'startup-probe.json').read_text(encoding='utf-8'))
        assert data['default_output_writable']
        assert not (documents / '丸丸小帮手输出').exists()
