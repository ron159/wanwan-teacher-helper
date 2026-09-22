from PIL import Image
from app.cli import run_cli


def test_cli_preview_then_execute(tmp_path, capsys):
    source = tmp_path / 'image.jpg'
    Image.new('RGB', (20, 20)).save(source)
    args = ['--tool', 'photo', '--input', str(source), '--output', str(tmp_path / 'out')]
    assert run_cli(args) == 0
    assert not (tmp_path / 'out').exists()
    assert run_cli([*args, '--execute']) == 0
    assert (tmp_path / 'out' / '处理报告.json').is_file()
