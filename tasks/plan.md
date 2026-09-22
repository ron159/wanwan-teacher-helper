# 丸丸小帮手实现与验收

依据用户指定的白皮书 v2.0-Python。Windows 10/11 x64，CPython 3.14、PySide6 Widgets、PyInstaller。默认离线、不改原件、禁止覆盖；UI 与 CLI 共用作业。

| 模块 | 责任 | 依赖 |
|---|---|---|
| safe-core | 类型参数、取消、原子输出、最小化报告 | 无 |
| photo | 方向、缩放、JPEG/透明 PNG、元数据 | safe-core |
| office | OOXML 检查、占用诊断、JPEG 定点优化 | safe-core, photo |
| organize | 分类复制、命名计划、完全重复、归档清单 | safe-core |
| template | 固定通知/周计划/标签/照片 DOCX/PPTX | safe-core, photo |
| pdf | 合并、拆分、抽页、旋转、照片打印 | safe-core |
| sheet | 同结构 Excel 汇总、字段与公式策略 | safe-core |
| media | 随包 FFmpeg、视频压缩、音频裁剪 | safe-core |
| desktop | 共享队列、参数、计划确认、后台进度和取消 | 各工具 |
| release | 锁版本、SBOM/许可、Windows onedir/onefile、烟测 | desktop |

顺序按上表；每个增量先写行为测试再实现。`python -m pytest` 验证功能，`ruff check .` 静态检查，`python main.py --self-test <目录>` 验证冻结产物。UI 使用 Qt 测试及截图。源文件哈希、冲突、坏图、恶意 ZIP、取消和结果可打开是硬门槛。

只实现白皮书明确允许的受控格式；任意 Office 转 PDF、OCR、AI 教育结论与无人值守发消息属于明确排除项。真实 Office/WPS、打印、普通用户断网现场与生产代码签名需要对应环境/证书，不用结构检查冒充。
