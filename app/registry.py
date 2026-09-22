from dataclasses import asdict
import json
from app.tools import photo, office, organize, template, pdf, sheet, media
from app.core.contracts import OfficeOptions, Progress
from app.core.jobs import validate_inputs
from app.core.safe_output import check_cancel

TOOLS = {
    'photo': ('照片准备', '校正方向、缩放照片，保留原件', photo.run),
    'office': ('文档瘦身', '先看占用，再保守优化 PPTX / DOCX', office.run),
    'organize': ('文件整理', '分类、命名、找重复与学期归档', organize.run),
    'template': ('材料制作', '把真实内容排成 Word / PPT 材料', template.run),
    'pdf': ('PDF 工具', '合并、拆分、抽页、旋转和照片打印', pdf.run),
    'sheet': ('表格汇总', '核对字段后合并同结构 Excel', sheet.run),
    'media': ('影音处理', '压缩视频、提取音频与按时间裁剪', media.run),
}


def preview(request, emit, cancel):
    validate_inputs(request, allow_empty=request.tool_id == 'template')
    lines = [f'工具：{TOOLS[request.tool_id][0]}', f'输入：{len(request.inputs)} 个文件',
             f'输出目录：{request.output_dir}', '原件保留；同名输出自动增加序号。']
    if request.tool_id == 'office':
        for index, source in enumerate(request.inputs, 1):
            check_cancel(cancel)
            try:
                info = office.inspect_package(source, cancel)
                sizes = ' / '.join(f'{k} {v["stored"] / 1024 / 1024:.2f} MB'
                                   for k, v in info['categories'].items())
                lines += [f'\n{source.name}', sizes,
                          f'JPEG 候选 {len(info["jpeg_candidates"])} 张；外部链接 {info["external_links"]} 个（不会访问）']
            except ValueError as exc:
                lines.append(f'{source.name}：{exc}')
            emit(Progress(index, len(request.inputs), '正在诊断文档占用'))
        if isinstance(request.options, OfficeOptions) and request.options.optimize:
            lines.append('\n将尝试有损重编码普通 JPEG；像素尺寸不变。带 EXIF/ICC/XMP 的 JPEG 保守跳过。请复核画面。')
    elif request.tool_id == 'organize' and request.options.mode in {'rename', 'classify'}:
        lines += [f'{src.name} → {dst.relative_to(request.output_dir)}'
                  for src, dst in organize.build_plan(request)]
    elif request.tool_id == 'template':
        template.validate_options(request.options)
        lines += ['模板内容：', request.options.title, request.options.class_name,
                  request.options.date, request.options.body, request.options.names]
    elif request.tool_id == 'pdf':
        lines.append('PDF 按队列顺序处理；原书签不保留。加密、表单、签名、注释/链接和自动动作会拒绝。')
    elif request.tool_id == 'media':
        lines.append('视频输出 MP4 (MPEG-4/AAC)；重编码有损。可裁剪，默认移除元数据。')
    else:
        lines.append('参数：' + json.dumps(asdict(request.options), ensure_ascii=False))
    return '\n'.join(lines)
