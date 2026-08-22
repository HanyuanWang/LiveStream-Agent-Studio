# 直播拆解 Agent

这是一个面向 2–4 小时直播录屏的本地 Agent。它把流程固化为：

```text
本地视频保留
  → ffmpeg 提取 16kHz 单声道 FLAC
  → 音频上传 OSS（或传入已有临时 URL）
  → 阿里云 Qwen 文件转写
  → 完整转写落盘并通过时间戳校验
  → 建立全局商品表
  → 事件切分与逐字稿对齐
  → 一个三列 Excel
```

## 最简单的使用方式

不需要输入 Python 命令：

1. 双击 `01_填写配置.cmd`，只在本机记事本中填写云端凭证。
2. 双击 `02_检查配置.cmd`，确认本地工具、百炼和 OSS 都显示为 `SET`。
3. 把直播视频拖到 `03_处理直播视频.cmd` 图标上。
4. 在 `workspace/output` 取得唯一交付文件 `视频名_拆解.xlsx`。

真实密钥只保存在被 `.gitignore` 排除的 `.env`，不要发送到聊天或提交到代码仓库。

关键约束已经写进程序：`transcription_validated` 阶段完成前，分析器不会启动。原视频从不上传；上传的是抽取后的音频。最终对外输出只有 `时间戳｜事件｜逐字稿` 三列 Excel，任务目录里的音频和 JSON 仅用于续跑、排错和以后回看原视频。

## 目录

```text
workspace/
  jobs/<任务ID>/       # 中间文件和状态
  output/*_拆解.xlsx   # 唯一交付物
```

## 首次设置

使用 Python 3.11+。在本目录执行：

```powershell
Copy-Item .env.example .env
python -m pip install -e .
# 需要自动上传 OSS 时再安装：
python -m pip install -e ".[aliyun-oss]"
```

然后只在本机 `.env` 填写密钥。建议 OSS 使用仅能访问指定 bucket/prefix 的 RAM 子账号或 STS 临时凭证。

检查环境：

```powershell
live-breakdown doctor
# 当前 Codex 工作区也可以不安装包，直接：
.\run.ps1 doctor
```

## 运行

让 Agent 自动抽音频、上传、转写、分析、导出：

```powershell
live-breakdown run "D:\录屏\某场直播.mp4"
# 或：.\run.ps1 run "D:\录屏\某场直播.mp4"
```

如果大文件上传期间网络中断，可从任务目录断点续跑，不重复抽取音频：

```powershell
.\run.ps1 resume-job ".\workspace\jobs\任务目录名"
```

已有可下载的临时音频 URL 时，可以跳过 OSS 上传：

```powershell
live-breakdown run "D:\录屏\某场直播.mp4" --audio-url "https://..."
```

如果已经有完整的 `transcript.json`（数组元素格式为 `start/end/text`），可从分析阶段开始：

```powershell
live-breakdown analyze-transcript transcript.json output.xlsx
```

## 当前第一版边界

- 已实现本地媒体检查、音频提取、任务状态闸门、DashScope 文件转写适配、OSS 适配、Qwen 事件分析和三列 Excel 导出。
- 云端调用需要你本地填好凭证后才能联调；`doctor` 不会产生 API 费用。
- Qwen3-ASR-Flash-Filetrans 使用单个 `input.file_url` 提交异步任务；结果链接会立即下载到任务目录，避免 24 小时临时链接过期。
- 完整转写验证后，Agent 才会把长稿按约 45 分钟/字符预算分块分析；先汇总全场商品表，再逐块切事件。分块不会提前到转写阶段。
- Excel 中的逐字稿不是模型改写结果，而是按事件句子索引从完整 ASR 原文回填，避免“优化文案”污染逐字稿。
- 最终事件段正常保持在 1–5 分钟；一分钟内同一商品的多种动作会合并为复合事件。只有整段输入本身不足 1 分钟时允许例外。
- 原视频分析将作为后续视觉复盘模块，届时按事件时间戳回看本地视频，不改变本版音频转写链路。
