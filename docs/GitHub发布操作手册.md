# GitHub 发布操作手册

## 一、创建仓库

1. 登录 GitHub，点击右上角 `+` → `New repository`。
2. Repository name 填 `liveagent-studio`。
3. Description 使用 `docs/GitHub项目介绍文案.md` 中的 About 简介。
4. 建议先选择 Private，完成最后一次隐私检查后再改为 Public。
5. 不要勾选自动创建 README、.gitignore 或 License，本文件夹已经准备好。

## 二、上传源码

把本文件夹中的全部内容上传到仓库根目录。确认网页中能看到 `.github`、`docs`、四个项目目录、`README.md` 和 `LICENSE`。

## 三、填写项目主页

在仓库右侧 About 区域点击齿轮，复制项目简介和 Topics。暂时不要填写在线 Website 地址，因为本项目是本机应用，`127.0.0.1` 不是公网网站。

## 四、生成 Windows EXE 发布包

1. 打开仓库的 `Actions`。
2. 选择 `Build Windows release`。
3. 点击 `Run workflow`。
4. 完成后在页面底部下载 `LiveAgent-Studio-Windows-x64` Artifact。

当前测试版使用 `v0.2.0-beta` 标签，工作流会自动把 ZIP 和 SHA256 文件附加到 GitHub Release。完整的仓库字段、Topics、Release 正文和对外介绍文案见 [GitHub项目介绍文案.md](GitHub项目介绍文案.md)。

## 五、公开前检查

逐项执行 `docs/隐私与发布检查清单.md`。尤其确认没有 `.env`、Cookie、Profile、日志、真实业务文件、个人姓名或本机路径。
