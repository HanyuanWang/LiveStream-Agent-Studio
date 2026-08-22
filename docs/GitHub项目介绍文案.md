# GitHub 上传清单与可复制文案

这份文件用于第一次创建并发布 LiveAgent Studio 仓库。尖括号中的内容需要替换，例如 `<你的 GitHub 用户名>`；其余文案可以直接复制。

## 一、真正需要上传的内容

### 上传到代码仓库

打开交付包中的：

```text
01_GitHub上传内容/LiveAgent-Studio/
```

把这个文件夹**里面的全部内容**上传到 GitHub 仓库根目录，包括：

```text
.github/
docs/
launcher/
liveagent-studio/
live_scout_agent/
live_breakdown_agent/
live_retro_agent/
scripts/
.gitignore
CHANGELOG.md
CONTRIBUTING.md
LICENSE
README.md
requirements-windows.txt
SECURITY.md
THIRD_PARTY_NOTICES.md
```

仓库首页应该直接看到 `README.md`，不要让 GitHub 根目录外面再套一层 `LiveAgent-Studio` 文件夹。

### 只上传到 GitHub Release

下面两个文件体积较大，只作为 Release 附件，**不要提交到代码仓库**：

```text
LiveAgent-Studio-Windows-x64.zip
LiveAgent-Studio-Windows-x64.zip.sha256
```

当前 V2 ZIP 的 SHA256：

```text
3AB2DCD56D62276D486C42BB54995C84B32FE95AFE68B73A9556D27CC7566FAC
```

### 绝对不要上传

- `.env`、API Key、AccessKey ID/Secret、安全令牌。
- Cookie、浏览器 Profile、蝉妈妈或抖音登录状态。
- `workspace`、SQLite 数据库、日志、录屏、音频、逐字稿和真实业务表格。
- `node_modules`、`dist`、`.runtime`、`__pycache__`。
- Windows ZIP 和 EXE 到源码提交历史中。
- 个人姓名、微信、手机号、邮箱或开发者本机绝对路径。

## 二、创建 GitHub 仓库时怎么填

### Repository name

```text
liveagent-studio
```

### Description / About

推荐中文版：

```text
Windows 本地直播电商 AI 工作台：主播发现、直播拆解、话术×流量复盘与短视频编导。
```

如果希望海外用户也能看懂，可以使用：

```text
Local-first Windows AI workspace for livestream commerce research, transcription, review and video scripting.
```

### Website

第一版留空。`127.0.0.1` 是用户电脑上的本地地址，不是可以填写到 GitHub About 的公开网站。

### Visibility

第一次建议选择 **Private**。完成上传、Actions 构建和隐私检查后，再到：

```text
Settings → General → Danger Zone → Change repository visibility
```

切换为 Public。

### 初始化选项

创建仓库时不要勾选：

- Add a README file
- Add .gitignore
- Choose a license

这些文件已经准备好了，重复创建会增加合并步骤。

## 三、GitHub Topics

在仓库右侧 About 区域点击齿轮，添加：

```text
livestream-commerce
ai-agent
windows
local-first
speech-to-text
creator-economy
douyin
qwen
oss
excel
```

Topics 使用小写英文和连字符，不要填写过于宽泛且与项目无关的热词。

## 四、推荐上传方法

推荐使用 Git，而不是把几百个文件逐个拖进网页。

在 `01_GitHub上传内容/LiveAgent-Studio` 文件夹中打开 PowerShell：

```powershell
git init
git branch -M main
git add .
git status
git commit -m "feat: publish LiveAgent Studio v0.2.0 beta"
git remote add origin https://github.com/<你的 GitHub 用户名>/liveagent-studio.git
git push -u origin main
```

执行 `git add .` 后一定先检查 `git status`。看到 `.env`、Cookie、Profile、workspace、录屏、业务 Excel、`node_modules` 或 `.runtime` 时，不要提交，先回到隐私清单排查。

如果 GitHub 要求登录，推荐使用 GitHub Desktop、Git Credential Manager 或 GitHub CLI，不要把个人访问令牌写进脚本或仓库文件。

## 五、第一次提交文字

Commit 标题：

```text
feat: publish LiveAgent Studio v0.2.0 beta
```

可选的完整 Commit 内容：

```text
feat: publish LiveAgent Studio v0.2.0 beta

- add four-agent local Windows workspace
- add local gateway and unified task center
- add Windows portable release workflow
- add security, privacy and contribution documentation
- add CI, Dependabot and release checksum generation
```

## 六、仓库设置建议

上传完成后进入 Settings：

### General

- Issues：开启。
- Discussions：第一版可以不开，确实准备维护社区时再开启。
- Wikis：暂时关闭，文档已经放在 `docs/`。
- Releases：保留开启。

### Actions → General

- Actions permissions：允许仓库中使用的 Actions。
- Workflow permissions：默认使用 Read repository contents permission。
- 只有 Windows Release 工作流需要创建 Release 时使用 `contents: write`。

### Security

建议开启：

- Dependabot alerts
- Dependabot security updates
- Secret scanning
- Push protection
- Private vulnerability reporting

如果某项在当前账号或仓库类型下不可用，可以先跳过，但不要删除仓库中的 `SECURITY.md`。

### Branch protection

项目只有一个维护者时，可以先设置：

- 禁止 force push 到 `main`。
- 合并前要求 CI 通过。
- 后续出现协作者后，再要求 Pull Request 审查。

## 七、第一次 Release 怎么发

### 推荐标签

```text
v0.2.0-beta
```

### Release title

```text
LiveAgent Studio v0.2.0-beta — Windows 本地直播电商 AI 工作台
```

### Release 类型

勾选：

```text
Set as a pre-release
```

当前仍是 Beta，不要标记为稳定正式版。

### Release 正文，可直接复制

```markdown
## LiveAgent Studio v0.2.0-beta

这是 LiveAgent Studio 的首个公开测试版本。它是一个面向直播电商团队的 Windows 本地 AI 工作台，统一提供主播发现、直播拆解、直播复盘和短视频编导能力。

### 主要功能

- 主播发现：管理关注领域、候选主播和达人拆解。
- 直播拆解：把完整直播视频转换为带秒级时间戳的逐字稿 Excel。
- 直播复盘：对齐直播逐字稿与巨量百应分钟流量，生成 Excel 和 Word 报告。
- 视频编导：根据用户提供的参考短视频链接生成真实逐字稿、原创脚本和分镜建议。
- 统一任务中心：查看任务状态、失败原因和输出文件。
- 本地设置页：配置用户自己的 DashScope、OSS，以及可选录制助手路径。

### Windows 安装

1. 下载本 Release 中的 `LiveAgent-Studio-Windows-x64.zip` 和同名 `.sha256` 文件。
2. 使用 SHA256 校验 ZIP。
3. 完整解压 ZIP，不要直接在压缩包内运行。
4. 双击 `LiveAgentStudio.exe`。
5. 程序会启动本机服务，并在默认浏览器打开 `http://127.0.0.1:4173/`。
6. 首次使用请进入“设置与连接”，填写并验证自己的阿里云配置。

### 重要说明

- 当前是 Beta 版本，建议先使用非敏感测试素材验证。
- EXE 尚未使用商业代码签名证书，Windows 可能显示 SmartScreen 提示。
- 云端转写会使用用户自己的阿里云服务并产生相应费用。
- 蝉妈妈和抖音功能取决于用户账号正常可见的页面、登录状态、会员权限及平台风控。
- 快抖直播录制助手为可选第三方依赖，不包含在本项目内。
- 项目不会绕过登录、验证码、会员限制或平台访问控制。

### 文件校验

请以本 Release 附带的 `LiveAgent-Studio-Windows-x64.zip.sha256` 为准。校验不一致或无法确认下载来源时，请不要运行。

### 反馈

普通问题请提交 Issue。请勿上传 API Key、Cookie、浏览器 Profile、真实业务文件或未经脱敏的日志。安全问题请通过仓库 Security 页面私密报告。
```

### Release 附件

拖入：

```text
LiveAgent-Studio-Windows-x64.zip
LiveAgent-Studio-Windows-x64.zip.sha256
```

不要把整个 `02_Windows发布成品` 文件夹上传，也不要把解压后的 1 GB 目录逐文件上传到 Release。

## 八、使用自动构建发布

仓库已经包含 `.github/workflows/windows-release.yml`。

源码上传后可以先进入：

```text
Actions → Build Windows release → Run workflow
```

验证 GitHub 能否成功构建。如果使用 Git 标签正式发布：

```powershell
git tag -a v0.2.0-beta -m "LiveAgent Studio v0.2.0-beta"
git push origin v0.2.0-beta
```

标签推送会触发 Windows Release 工作流。不要在自动工作流和手工流程中重复上传两个同名附件；选择其中一种完成最终 Release 即可。

## 九、对外介绍文字

### 一句话介绍

```text
LiveAgent Studio：把主播发现、长直播逐字稿、话术×流量复盘和短视频编导整合到一个 Windows 本地工作台。
```

### 稍长介绍

```text
LiveAgent Studio 是面向直播电商团队的 Windows 本地 AI 工作台。它把主播发现、直播拆解、直播复盘和短视频编导放进统一入口：从账号正常可见的榜单管理候选主播，把长直播转成带时间戳的结构化逐字稿，对齐分钟流量分析不同话术时段，再根据用户选定的参考短视频生成原创脚本与分镜。任务、登录状态和输出默认保存在本机，云端能力使用用户自己配置的阿里云服务。
```

### 社交平台发布文案

```text
我把直播团队经常分散在榜单、录屏、逐字稿、流量表和脚本文件里的工作，整理成了一个 Windows 本地 AI 工作台：LiveAgent Studio。

目前包含四个模块：主播发现、直播拆解、话术×流量复盘、短视频编导。双击 EXE 后会在浏览器打开本机工作台，任务和输出默认留在自己的电脑上；需要转写时使用用户自己配置的阿里云服务。

现在发布的是 v0.2.0-beta，欢迎用非敏感素材试用、提交可复现问题，也欢迎一起改进文档和代码。

GitHub：<你的仓库链接>
```

## 十、公开前最后检查

- [ ] 仓库首页 README 正常显示，Mermaid 架构图可以渲染。
- [ ] About、Topics、License 和 Release 信息已填写。
- [ ] 仓库里没有 `.env`、Cookie、Profile、workspace 和业务文件。
- [ ] GitHub Actions 的 CI 全部通过。
- [ ] Windows Release 工作流成功。
- [ ] Release 同时包含 ZIP 和 `.sha256`。
- [ ] Release 标记为 Pre-release。
- [ ] 从 Release 重新下载 ZIP，校验后在另一台或干净环境 Windows 电脑试运行。
- [ ] 已启用 Secret scanning、Push protection 和 Private vulnerability reporting。
- [ ] Issue 模板能正常打开，安全问题指向私密渠道。

完成以上检查后，再把仓库从 Private 切换为 Public。
