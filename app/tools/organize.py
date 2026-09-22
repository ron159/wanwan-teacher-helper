from collections import defaultdict
import hashlib
import json
from zipfile import ZipFile, ZIP_DEFLATED
from app.core.contracts import FileResult, OrganizeOptions, Progress
from app.core.jobs import validate_inputs, success, run_files
from app.core.safe_output import SafeOutputWriter, check_cancel, safe_name

GROUPS = {'照片': {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.bmp'},
          '文档': {'.doc', '.docx', '.ppt', '.pptx', '.pdf', '.txt'},
          '表格': {'.xls', '.xlsx', '.csv'},
          '影音': {'.mp4', '.mov', '.avi', '.mp3', '.wav', '.m4a'}}


def file_group(path):
    return next((name for name, extensions in GROUPS.items() if path.suffix.lower() in extensions), '其他')


def build_plan(request):
    safe_name(request.options.prefix)
    plan = []
    for index, source in enumerate(request.inputs, 1):
        if request.options.mode == 'rename':
            relative = f'{request.options.prefix}_{index:04d}{source.suffix.lower()}'
            target = request.output_dir / relative
        else:
            target = request.output_dir / file_group(source) / source.name
        safe_name(target.name)
        plan.append((source, target))
    return plan


def file_hash(path, cancel):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            check_cancel(cancel)
            digest.update(chunk)
    return digest.hexdigest()


def run(request, emit, cancel):
    validate_inputs(request)
    if not isinstance(request.options, OrganizeOptions):
        raise ValueError('文件整理参数错误')
    mode = request.options.mode
    if mode in {'classify', 'rename'}:
        plan = build_plan(request)

        def process(source, req, index, stop):
            with SafeOutputWriter(plan[index - 1][1], req.inputs) as writer:
                with source.open('rb') as src, writer.path.open('wb') as dst:
                    while chunk := src.read(1024 * 1024):
                        check_cancel(stop)
                        dst.write(chunk)
                def verify(path):
                    if file_hash(source, stop) != file_hash(path, stop):
                        raise ValueError('复制校验失败，原文件可能已变化')
                output = writer.commit(verify, stop)
            return success(source, output, '副本已保存，内容哈希一致')
        return run_files(request, process, emit, cancel)
    if mode == 'duplicates':
        sizes = defaultdict(list)
        for index, source in enumerate(request.inputs, 1):
            check_cancel(cancel)
            sizes[source.stat().st_size].append((index, source))
        groups = []
        for bucket in sizes.values():
            if len(bucket) < 2:
                continue
            hashes = defaultdict(list)
            for index, path in bucket:
                hashes[file_hash(path, cancel)].append(index)
                emit(Progress(index, len(request.inputs), '正在比较文件内容'))
            groups.extend(group for group in hashes.values() if len(group) > 1)
        return (FileResult(request.inputs[0], None, 'success',
                           f'找到 {len(groups)} 组完全重复文件；未删除任何文件',
                           details={'duplicate_groups': groups}),)
    if mode == 'archive':
        manifest = []
        with SafeOutputWriter(request.output_dir / '学期归档.zip', request.inputs) as writer:
            with ZipFile(writer.path, 'w', ZIP_DEFLATED) as archive:
                for index, source in enumerate(request.inputs, 1):
                    name = f'{file_group(source)}/{index:04d}_{source.name}'
                    digest = hashlib.sha256()
                    with source.open('rb') as src, archive.open(name, 'w') as dst:
                        while chunk := src.read(1024 * 1024):
                            check_cancel(cancel)
                            digest.update(chunk)
                            dst.write(chunk)
                    manifest.append({'file': name, 'sha256': digest.hexdigest()})
                    emit(Progress(index, len(request.inputs), '正在归档副本'))
                archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            def verify(path):
                with ZipFile(path) as archive:
                    for record in manifest:
                        digest = hashlib.sha256()
                        with archive.open(record['file']) as stream:
                            while chunk := stream.read(1024 * 1024):
                                check_cancel(cancel)
                                digest.update(chunk)
                        if digest.hexdigest() != record['sha256']:
                            raise ValueError('归档校验失败')
            output = writer.commit(verify, cancel)
        return (success(request.inputs[0], output, f'已归档 {len(manifest)} 个文件，附 SHA-256 清单'),)
    raise ValueError('未知整理模式')
