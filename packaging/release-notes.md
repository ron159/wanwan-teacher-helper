丸丸小帮手 v0.3.4，新增 Apple Silicon macOS 应用。现有 Python 依赖版本与 Windows 影音引擎保持不变。

macOS 15 及以上的 Apple Silicon Mac 下载 `WanwanTeacherHelper-v0.3.4-macos-arm64.zip`，解压后将 `.app` 拖到“应用程序”使用。内含独立 Python/Qt 和从 FFmpeg 8.1.3 固定官方源码编译的原生影音引擎，无需安装 Python 或 Homebrew。Mac 版采用 ad-hoc 签名，尚未进行 Apple Developer ID 签名及公证；从 GitHub Releases 手动下载新版，不会误下载 Windows EXE。

Windows 下载 `WanwanTeacherHelper-v0.3.4-windows-x64.exe` 即可运行，延续未签名自用发行方式。请核对各平台 SHA-256 清单。通信簿、照片批量方向与尺寸调整、Word 多图排版、文档瘦身及其他工具继续提供。原件保留，结果另存。

双平台 CI 检查功能测试、冻结应用启动和 30 种处理模式，macOS 验证移除 Python/Homebrew 后的启动与 ad-hoc 签名；Windows 继续验证普通用户离线环境。macOS 源码归档、许可证、SBOM、签名状态与自检报告一并提供。

从 v0.3.1 及更早版本首次自动更新时，旧更新器仍可能在替换后重启时提示找不到 `python314.dll`。关闭提示，再从原位置手动打开程序即可；也可直接下载本版 EXE。v0.3.2 已包含重启修复，本版继续保留。

真实 Office/WPS 画面、字体、动画、播放、打印及园所现场仍需在对应环境验收。PDF 不保留书签，表单、签名、注释和链接不处理；视频使用 MPEG-4/AAC。请先用材料副本试用并复核输出。
