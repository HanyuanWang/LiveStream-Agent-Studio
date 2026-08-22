# Contributing

感谢参与 LiveAgent Studio。提交代码前请先搜索已有 Issue，并尽量把一个 PR 控制在一个明确问题内。

## 本地检查

1. 前端目录运行 `npm ci` 和 `npm test`。当前严格 ESLint 仍有存量类型与无障碍问题，修复相关代码时请同时减少对应告警。
2. 在三个 Python Agent 目录运行现有测试。
3. 不得提交 `.env`、API Key、Cookie、浏览器 Profile、workspace、日志或真实业务文件。
4. 涉及本地网关、文件路径、登录状态或外部进程时，请在 PR 中说明安全边界和人工验证方法。

安全漏洞不要提交公开 Issue，请按照 `SECURITY.md` 私密报告。
