from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal
from threading import Event


@dataclass(frozen=True)
class PhotoOptions:
    max_edge: int = 1920
    quality: int = 85
    prefix: str = '照片'
    keep_metadata: bool = False
    rotation: int = 0
    orientation: str = 'original'


@dataclass(frozen=True)
class OfficeOptions:
    optimize: bool = False
    quality: int = 85
    aggressive: bool = False


@dataclass(frozen=True)
class OrganizeOptions:
    mode: str = 'classify'
    prefix: str = '材料'


@dataclass(frozen=True)
class PdfOptions:
    mode: str = 'merge'
    pages: str = ''
    rotation: int = 90


@dataclass(frozen=True)
class TemplateOptions:
    layout: str = 'photo_docx'
    title: str = '活动记录'
    class_name: str = ''
    date: str = ''
    body: str = ''
    names: str = ''
    rows: int = 3
    columns: int = 2
    page_orientation: str = 'portrait'
    image_size_mode: str = 'auto'
    image_width_cm: float = 7.0
    image_height_cm: float = 5.0
    keep_aspect_ratio: bool = True
    rotation: int = 0
    orientation: str = 'original'


@dataclass(frozen=True)
class SheetOptions:
    sheet_name: str = ''
    formula_policy: str = 'reject'


@dataclass(frozen=True)
class MediaOptions:
    mode: str = 'video'
    max_height: int = 720
    quality: int = 5
    start: float = 0
    duration: float = 0


Options = PhotoOptions | OfficeOptions | OrganizeOptions | PdfOptions | TemplateOptions | SheetOptions | MediaOptions


@dataclass(frozen=True)
class JobRequest:
    tool_id: str
    inputs: tuple[Path, ...]
    output_dir: Path
    options: Options


@dataclass(frozen=True)
class Progress:
    completed: int
    total: int
    message: str


@dataclass(frozen=True)
class FileResult:
    source: Path
    output: Path | None
    status: Literal['success', 'skipped', 'failed', 'cancelled']
    message: str
    bytes_before: int = 0
    bytes_after: int | None = None
    details: dict = field(default_factory=dict)


Emit = Callable[[Progress], None]
Processor = Callable[[Path, JobRequest, int, Event], FileResult]
