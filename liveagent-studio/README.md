# LiveAgent Studio Web UI

这是 LiveAgent Studio 的本地网页界面。它不是独立云站点：页面运行在
`127.0.0.1:4173`，通过 `127.0.0.1:8785` 调用本机 Python 网关。

## 开发

```powershell
npm ci
npm run dev
```

常用命令：

- `npm run build`：生成本地发布构建。
- `npm test`：构建并验证主要页面输出。
- `npm run lint`：运行前端静态检查。

不要把 `.env`、浏览器 Profile、Cookie、任务 workspace 或真实业务文件提交到仓库。
完整的安装、架构和发布说明请查看仓库根目录 README 与 `docs/`。
