import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from app.core.contracts import FileResult, MediaOptions
from app.core.jobs import validate_inputs, run_files, success
from app.core.safe_output import SafeOutputWriter, check_cancel
from app.resources import resource
from app.core.engine_cache import prepare_engine
from threading import Event


def engines(cancel=None):
    cancel = cancel if cancel is not None else Event()
    if not getattr(sys, 'frozen', False) and os.name != 'nt':
        found = tuple(shutil.which(name) for name in ('ffmpeg', 'ffprobe'))
        if all(found):
            return found
    manifest = resource('vendor/ffmpeg/manifest.json')
    local = os.environ.get('LOCALAPPDATA')
    if not local:
        raise ValueError('无法定位当前用户的应用数据目录')
    base = prepare_engine(manifest, Path(local) / 'WanwanTeacherHelper' / 'engines', cancel)
    return str(base / 'bin/ffmpeg.exe'), str(base / 'bin/ffprobe.exe')


def execute(args, cancel, timeout=3600):
    kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    with subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, shell=False, **kwargs) as process:
        elapsed = 0
        try:
            while True:
                check_cancel(cancel)
                try:
                    output, _ = process.communicate(timeout=.2)
                    break
                except subprocess.TimeoutExpired:
                    elapsed += .2
                    if elapsed >= timeout:
                        raise ValueError('影音处理超时，请缩短素材或降低分辨率')
            if process.returncode:
                raise ValueError('影音引擎无法处理文件，请检查格式、可用空间与文件完整性')
            return output
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise


def probe(path, cancel):
    _, ffprobe = engines(cancel)
    return json.loads(execute([ffprobe, '-v', 'error', '-protocol_whitelist', 'file,pipe',
                              '-show_entries', 'format=duration:stream=codec_type,width,height',
                              '-of', 'json', str(Path(path).resolve())], cancel, 30))


def process(source, request, index, cancel):
    if source.suffix.lower() not in {'.mp4', '.mov', '.mkv', '.avi', '.wmv', '.webm', '.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'}:
        raise ValueError('不支持此影音格式；不接受播放列表或网络地址')
    options = request.options
    info = probe(source, cancel)
    duration = float(info.get('format', {}).get('duration', 0))
    video = options.mode == 'video'
    needed = 'video' if video else 'audio'
    if not any(stream.get('codec_type') == needed for stream in info.get('streams', [])):
        raise ValueError('素材不包含所选类型的影音流')
    if duration <= options.start:
        raise ValueError('开始时间超过素材时长')
    if options.duration and options.start + options.duration > duration + .1:
        raise ValueError('裁剪结束时间超过素材时长')
    ffmpeg, _ = engines(cancel)
    suffix = '.mp4' if video else ('.wav' if options.mode == 'wav' else '.m4a')
    with SafeOutputWriter(request.output_dir / f'{source.stem[:80]}_分享{suffix}', request.inputs) as writer:
        args = [ffmpeg, '-v', 'error', '-nostdin', '-y', '-protocol_whitelist', 'file,pipe',
                '-i', str(source.resolve()), '-ss', str(options.start)]
        if options.duration:
            args += ['-t', str(options.duration)]
        args += ['-map_metadata', '-1', '-map_chapters', '-1', '-threads', '2']
        if video:
            args += ['-map', '0:v:0', '-map', '0:a:0?', '-vf',
                     rf"scale=-2:trunc(min(ih\,{options.max_height})/2)*2", '-c:v', 'mpeg4',
                     '-q:v', str(options.quality), '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                     '-b:a', '128k', '-movflags', '+faststart']
        else:
            args += ['-map', '0:a:0', '-vn', '-c:a', 'pcm_s16le'] if suffix == '.wav' else [
                '-map', '0:a:0', '-vn', '-c:a', 'aac', '-b:a', '128k']
        args += [str(writer.path.resolve())]
        execute(args, cancel)
        result_info = probe(writer.path, cancel)
        if float(result_info.get('format', {}).get('duration', 0)) <= 0:
            raise ValueError('输出时长校验失败')
        # Decode all frames to verify the produced media, not just its container header.
        execute([ffmpeg, '-v', 'error', '-xerror', '-nostdin', '-protocol_whitelist', 'file,pipe',
                 '-i', str(writer.path.resolve()), '-f', 'null', '-'], cancel)
        if video and not options.start and not options.duration and writer.path.stat().st_size >= source.stat().st_size:
            return FileResult(source, None, 'skipped', '无需优化：重编码未减小体积', source.stat().st_size)
        output = writer.commit(cancel=cancel)
    return success(source, output, '影音副本已输出并完成全帧解码检查')


def run(request, emit, cancel):
    validate_inputs(request)
    o = request.options
    if (not isinstance(o, MediaOptions) or o.mode not in {'video', 'audio', 'wav'}
            or not 144 <= o.max_height <= 2160 or not 2 <= o.quality <= 15
            or not all(math.isfinite(x) and x >= 0 for x in (o.start, o.duration))):
        raise ValueError('影音参数无效')
    engines(cancel)
    return run_files(request, process, emit, cancel)
