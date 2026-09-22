# 白皮书技术目标与验收对应

| 目标 | 实现 | 验证 |
|---|---|---|
| M0 单 EXE 无 Python 运行 | main.py、scripts/build.py、Windows CI | onedir/onefile 内置 --self-test；移除 Python PATH |
| M1 安全基础 | core/contracts、jobs、safe_output、reports | 同名冲突、输入同路径、取消、验证失败、临时清理 |
| M2 照片准备 | tools/photo、ui/photo_preview | 方向、透明、坏图隔离、动画跳过、预览不写文件 |
| M3 文档诊断 | tools/office.inspect_package | 分类按压缩后体积、容器开销、外部引用数、危险 ZIP/XML |
| M4 保守瘦身 | tools/office.process | 仅 JPEG、更小才提交、原件不变、未改成员哈希一致 |
| M5 文件整理 | tools/organize | 分类/命名复制、计划预览、大小分桶 SHA-256 重复、归档清单 |
| M6 模板与 PDF | tools/template、pdf | Word/PPT 可重开、说明保留、转义、页序/旋转/拆分和中途取消 |
| M7 Excel 与视频 | tools/sheet、media | 同结构/编号/公式策略、标题不转公式、真实影音全帧解码 |
| M8 发行 | scripts/notices、fetch_ffmpeg、standard_user_smoke、release workflow | 版本锁定、引擎哈希、SBOM/许可、非管理员、网络受限运行 |
| 统一 UI 与后台 | ui/window、forms、worker | 导航、队列顺序、确认前不写、完整处理链 Qt 自动测试 |
| CLI | app/cli | 默认预览，显式 --execute 后使用相同工具 |

输出只在用户选择的目录与用户临时目录落盘，运行时无联网下载/遥测/上传。照片元数据默认移除，归档清单按功能保留文件名；结果与报告仍应妥善保存。

## 诚实验收边界

- Windows CI 是 Windows Server 2022 执行环境；非管理员验收创建临时普通账户，主 EXE 出站被防火墙阻断，影音协议被限制为 file/pipe。不能将此描述为所有 Windows 10/11 实机、整机断网均已验证。
- 自动化样本由测试生成，不冒充 50–100 份授权园所真实 Office/WPS 样本；真实文档视觉、字体、裁剪、动画、视频播放及打印需人工复核。
- 未提供生产 Authenticode 证书，EXE 未签名；发布提供 SHA-256，定位为试用发行。
- 自动更新没有列入白皮书 M0–M8 当前实现任务，应用不联网自更新。
- 不实现白皮书明确排除的任意 Office 转 PDF、OCR、儿童自动评价、自动发送消息和旧格式猜测转换。
