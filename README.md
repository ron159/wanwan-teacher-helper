# 丸丸小帮手电脑版

面向幼儿园教师的离线文件助手。Python + PySide6，Windows 单 EXE，无需安装 Python 或 Office。保留原件、输出不覆盖、先预览再执行，支持进度、取消与逐文件报告。

## 功能

- 照片：EXIF 方向校正、缩放、规范命名；透明图输出 PNG，普通照片 JPEG；默认去除 EXIF。
- 文档：DOCX/PPTX 占用诊断；保守模式仅优化普通 JPEG，激进模式将 JPEG/PNG 最长边缩至 1280 像素、PNG 减至 64 色并重新压缩容器。激进模式有损且移除图片元数据，原件始终保留；无收益不输出。
- 整理：分类复制、批量命名副本、SHA-256 完全重复报告、带清单 ZIP 归档；不删除文件。
- 材料：固定 A4 照片 Word、照片 PPT、通知、周计划、姓名标签/座位卡、奖状。
- PDF：合并、逐页拆分、抽页重排、旋转、照片转 A4；原书签不保留；加密/表单/签名/注释链接/动作拒绝。
- Excel：同字段同顺序 XLSX 汇总，编号文本和日期格式保留；默认拒绝公式，可明确选用缓存值。
- 影音：随包 FFmpeg/ffprobe、MP4 视频压缩、M4A/WAV 音频、时间裁剪；输出后全帧解码检查。

## 使用

从 Releases 下载 `WanwanTeacherHelper-*-windows-x64.exe`，双击启动。选工具 → 添加文件 → 设置输出目录 → 预览计划 → 确认。请使用“查看报告”核对结果。输出目录包含结果和 JSON 报告；报告、归档清单仍须按园所要求妥善保管。

单文件程序会在用户临时目录释放依赖，退出后由 PyInstaller 清理。首次启动请为包含影音引擎的大体积程序预留时间和磁盘空间。输入文件处理期间请勿移动或修改。

界面跟随 Windows 的浅色/暗色模式切换。每次正常启动会向本仓库 GitHub Releases 查询新版本；确认后下载、校验并替换 EXE。离线时文件处理仍可使用，材料不会上传。

## 开发与测试

```sh
python -m venv .venv
# 激活环境后
python -m pip install -r requirements-lock.txt
python main.py
python -m pytest -q
ruff check .
python main.py --self-test artifacts/smoke
```

macOS/Linux 开发环境的影音测试可使用 PATH 中的 ffmpeg/ffprobe；发行 Windows EXE 只使用哈希验证的随包引擎。仅自动更新访问 GitHub；文件处理不联网，也无遥测或材料上传。

CLI 默认只预览：`python main.py --tool photo --input 照片.jpg --output 输出目录`；核对后追加 `--execute`。各工具使用同一执行接口，`--options` 可传入参数 JSON。

Windows 构建：

```powershell
python scripts/fetch_ffmpeg.py
python scripts/build.py onedir
python scripts/build.py onefile
```

CI 在 Windows 执行测试，然后分别启动目录版和单 EXE，使用合成材料实际运行所有模块并生成截图、结果与源文件哈希检查。除明确授权的 `v0.2.0-preview.1`、`v0.2.0-preview.2` 和 `v0.3.0` 自用未签名版外，标签发布必须先通过生产签名和时间戳校验，再执行单 EXE 验收；配置见 [签名说明](packaging/signing.md)。Release 附 SHA-256、SBOM、第三方许可与验证记录。

## 已知边界

仅支持白名单格式；不支持旧 DOC/PPT、宏、加密/签名 Office、任意 Office 转 PDF、OCR、人脸识别或自动教育评价。文档结构校验不能替代 Office/WPS 打开、字体换行、动画与打印的人工复核。首次发布为试用版本，尚不代表园所生产验收。

未配置生产代码签名身份，v0.1.0、v0.2.0-preview.1、v0.2.0-preview.2 与 v0.3.0 自用 EXE 未做 Authenticode 签名；请从本仓库下载并核对 SHA-256。除上述明确授权的标签外，新标签发布会因缺少签名身份而阻断。CI 使用新建的非管理员账户、移除 Python 的 PATH，并阻断测试账户所有进程出站执行全部 30 个模式组合；同时测量启动、解包与缓存空间并核对退出清理。影音引擎只允许本地协议。物理断网实机与真实 Office/WPS 样本验收仍需在对应环境执行。

第三方许可证、库替换与重建说明见 [licenses/NOTICE.md](licenses/NOTICE.md)。本地白皮书目录 `local_doc/` 和 `locald_doc/` 均不上传。

### 文件夹照片与 Word 多图排版

在「照片准备」点击「添加文件夹」，可批量缩放、顺时针旋转 90°/180°/270°，或将横竖混合图片统一为横向/竖向。先校正 EXIF，再执行旋转，最后统一横竖方向；它不会识别人物是否正立，可通过「查看照片效果」检查。缩放保持比例，小图不放大，原件保留。

需要每页多张照片时，直接在「材料制作」选择「A4 照片材料 · Word」，添加图片文件夹，输入每页行数和列数（各 1–10，默认 3 行 × 2 列），选择 A4 纸张横向或纵向。图片尺寸可自动等比例适配网格，也可手动输入宽高（厘米）；手动模式默认等比例适配所填范围，取消保持比例则拉伸至精确宽高。超过网格可用空间会提示调整，过密网格会拒绝。设置旋转方向、标题后预览并直接生成 Word，按队列顺序排版并自动分页，无需先导出图片。文件夹导入读取当前层的常见图片格式，不递归子目录；单份 Word 最多 200 张。
