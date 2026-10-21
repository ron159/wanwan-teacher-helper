from pathlib import Path
import sys


def resource(relative):
    name = Path(relative)
    if name.is_absolute() or '..' in name.parts:
        raise ValueError('资源路径必须为包内相对路径')
    base = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
    path = (base / name).resolve()
    roots = [base.resolve()]
    if (getattr(sys, 'frozen', False) and sys.platform == 'darwin'
            and base.name == 'Frameworks' and base.parent.name == 'Contents'):
        # PyInstaller links data from Frameworks into its sibling Resources directory.
        roots.append((base.parent / 'Resources').resolve())
    if not any(path.is_relative_to(root) for root in roots) or not path.is_file():
        raise FileNotFoundError(f'缺少随包资源：{relative}')
    return path
