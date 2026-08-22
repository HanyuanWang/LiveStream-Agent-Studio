# Third-party notices

LiveAgent Studio 的 Windows 发布包会包含下列独立第三方运行时。它们分别受各自许可证约束，并不因本项目采用 MIT License 而改变。

- Python 3.12：Python Software Foundation License。来源：https://www.python.org/downloads/windows/
- Node.js 22：Node.js 各贡献者及其依赖许可证。来源：https://nodejs.org/
- FFmpeg：发布包内 `tools/ffmpeg/.../LICENSE.txt` 所列 GPLv3 许可。对应构建来源：https://github.com/BtbN/FFmpeg-Builds
- Python 与 npm 依赖：具体版本及许可证见 `requirements-windows.txt`、`liveagent-studio/package-lock.json` 和各 Python 包元数据。

发布 ZIP 保留 FFmpeg 构建附带的许可证文件。重新分发前，请同时保留本文件和各第三方组件自带的许可证。
