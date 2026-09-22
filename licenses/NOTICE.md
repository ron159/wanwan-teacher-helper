# 第三方组件与可重建分发

本程序使用 PySide6/Qt（LGPLv3）、FFmpeg LGPL shared 构建、Pillow、pypdf、openpyxl、python-docx、python-pptx、defusedxml 及其依赖。完整的安装元数据、许可证文本和 CycloneDX SBOM 在 Windows 构建时自动收集，随 EXE 内部及 Release 的第三方许可归档分发。

- Qt/PySide6： https://code.qt.io/cgit/pyside/pyside-setup.git/ （按锁定版本检出）； https://download.qt.io/archive/qt/ 。Qt 动态库由 PyInstaller 打包释放；允许为调试 LGPL 库修改而进行逆向工程。
- FFmpeg： https://github.com/FFmpeg/FFmpeg/tree/n8.1.3 。确切 BtbN 构建、下载 URL 与 SHA-256 见 packaging/ffmpeg-lock.json，完整引擎文件、DLL、许可证、预设、构建参数和清单随包。
- BtbN 构建脚本与依赖来源： https://github.com/BtbN/FFmpeg-Builds 。构建版本仅使用 LGPL shared 变体，不包含 GPL 编码器；实际构建配置在发行许可证包中保存。
- Python： https://www.python.org/downloads/source/ 。Python 及二进制依赖的原始许可在 licenses/generated 中收集。

在 Windows 安装锁定依赖后运行 `python scripts/build.py onedir` 可重建目录版并替换 LGPL 动态库；`python scripts/build.py onefile` 重建单文件版。用户可取得本项目全部源码及构建脚本。不得将第三方组件的许可证视为本项目原创代码的许可证。

原始资料与报告完全在本机处理。此软件不附带 Microsoft Office/WPS、商业字体或商业素材。
