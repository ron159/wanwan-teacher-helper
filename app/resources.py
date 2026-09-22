from pathlib import Path
import sys


def resource(relative):
    name = Path(relative)
    if name.is_absolute() or '..' in name.parts:
        raise ValueError('资源路径必须为包内相对路径')
    base = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise FileNotFoundError(f'缺少随包资源：{relative}')
    return path
