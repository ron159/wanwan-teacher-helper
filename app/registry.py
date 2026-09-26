from dataclasses import asdict
import json
from app.tools import photo, office, organize, template, pdf, sheet, media
from app.core.contracts import OfficeOptions, Progress
from app.core.jobs import validate_inputs
from app.core.safe_output import check_cancel

TOOLS = {
    'photo': ('照片准备', '校正方向、缩放照片，保留原件', photo.run),
    'office': ('文档瘦身', '诊断占用；保守或激进压缩 DOCX / PPTX', office.run),
    'organize': ('文件整理', '分类、批量命名、重复检测与 ZIP 归档', organize.run),
    'template': ('材料制作', '生成 Word / PPT 材料', template.run),
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
                          f'JPEG 候选 {len(info["jpeg_candidates"])} 张；PNG 候选 {len(info["png_candidates"])} 张；外部链接 {info["external_links"]} 个（不会访问）']
            except ValueError as exc:
                lines.append(f'{source.name}：{exc}')
            emit(Progress(index, len(request.inputs), '正在诊断文档占用'))
        if isinstance(request.options, OfficeOptions) and request.options.aggressive:
            lines.append('\n激进模式：JPEG/PNG 最长边缩至 1280 像素，JPEG 按所选质量重编码，PNG 减至 64 色；图片元数据将移除。文字、动画、矢量图和嵌入对象保留；画质与色彩可能下降，请复核每页。')
        elif isinstance(request.options, OfficeOptions) and request.options.optimize:
            lines.append('\n将尝试有损重编码普通 JPEG；像素尺寸不变。带 EXIF/ICC/XMP 的 JPEG 保守跳过。请复核画面。')
    elif request.tool_id == 'organize' and request.options.mode in {'rename', 'classify'}:
        lines += [f'{src.name} → {dst.relative_to(request.output_dir)}'
                  for src, dst in organize.build_plan(request)]
    elif request.tool_id == 'template':
        template.validate_options(request.options)
        if request.options.layout == 'photo_docx':
            count = request.options.rows * request.options.columns
            opts = request.options
            paper = '横向' if opts.page_orientation == 'landscape' else '纵向'
            lines.append(f'A4 {paper} · {opts.rows} 行 × {opts.columns} 列；每页 {count} 张，共 {(len(request.inputs) + count - 1) // count} 页。')
            if opts.image_size_mode == 'auto':
                lines.append('图片自动等比例适配网格，不裁剪、不拉伸。')
            else:
                fit = '等比例适配此范围' if opts.keep_aspect_ratio else '拉伸至此尺寸（可能变形）'
                lines.append(f'图片宽 {opts.image_width_cm:g} × 高 {opts.image_height_cm:g} 厘米；{fit}。')
        if request.options.layout.startswith('photo_'):
            direction = {'original': '保持横竖方向', 'landscape': '统一横向', 'portrait': '统一竖向'}[request.options.orientation]
            lines.append(f'自动校正 EXIF 后顺时针旋转 {request.options.rotation}°，然后{direction}。')
        lines += ['模板内容：', request.options.title, request.options.class_name,
                  request.options.date, request.options.body, request.options.names]
    elif request.tool_id == 'pdf':
        lines.append('PDF 按队列顺序处理；原书签不保留。加密、表单、签名、注释/链接和自动动作会拒绝。')
    elif request.tool_id == 'media':
        lines.append('视频输出 MP4 (MPEG-4/AAC)；重编码有损。可裁剪，默认移除元数据。')
    else:
        lines.append('参数：' + json.dumps(asdict(request.options), ensure_ascii=False))
    return '\n'.join(lines)
