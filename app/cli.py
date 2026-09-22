"""Same tools as the GUI, with explicit --execute after a preview."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import signal
from threading import Event
from app.core.contracts import (JobRequest, PhotoOptions, OfficeOptions, OrganizeOptions,
                                TemplateOptions, PdfOptions, SheetOptions, MediaOptions)
from app.core.reports import write_report
from app.core.jobs import friendly_error
from app.registry import TOOLS, preview


def run_cli(argv):
    parser = argparse.ArgumentParser(description='丸丸小帮手离线批处理；默认只预览')
    parser.add_argument('--tool', required=True, choices=list(TOOLS))
    parser.add_argument('--input', action='append', default=[], help='可重复指定输入文件')
    parser.add_argument('--output', required=True)
    parser.add_argument('--options', default='{}', help='对应工具参数的 JSON 对象')
    parser.add_argument('--execute', action='store_true', help='确认执行并写入新副本')
    args = parser.parse_args(argv)
    options_types = {'photo': PhotoOptions, 'office': OfficeOptions, 'organize': OrganizeOptions,
                     'template': TemplateOptions, 'pdf': PdfOptions, 'sheet': SheetOptions, 'media': MediaOptions}
    cancel = Event()
    previous = signal.signal(signal.SIGINT, lambda *_: cancel.set())
    try:
        values = json.loads(args.options)
        options = options_types[args.tool](**values)
        request = JobRequest(args.tool, tuple(Path(p).resolve() for p in args.input),
                             Path(args.output).resolve(), options)
        if not args.execute:
            print(preview(request, lambda _: None, cancel))
            return 0
        results = TOOLS[args.tool][2](request, lambda _: None, cancel)
        report = write_report(request.output_dir, request.tool_id, results)
        print(json.dumps({'results': [asdict(r) for r in results], 'report': report},
                         default=str, ensure_ascii=False, indent=2))
        return 1 if any(r.status in {'failed', 'cancelled'} for r in results) else 0
    except Exception as exc:
        print(friendly_error(exc))
        return 1
    finally:
        signal.signal(signal.SIGINT, previous)
