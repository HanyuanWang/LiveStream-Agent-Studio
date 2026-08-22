from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Settings


DEFAULT_STATE: dict[str, Any] = {
    "phase": "not_configured",
    "message": "尚未建立蝉妈妈专用登录会话",
    "logged_in": False,
    "busy": False,
    "download_path": "",
    "imported": False,
}

CHANMAMA_CATEGORIES = (
    "服饰内衣", "鞋靴箱包", "食品饮料", "美妆护肤", "运动户外", "日用百货",
    "家居家纺", "母婴用品", "医药保健", "3C数码", "厨卫家电", "家具建材",
    "珠宝饰品", "玩具乐器", "图书教育", "礼品文创", "生鲜蔬果", "鲜花绿植",
    "宠物用品", "汽配摩托", "钟表配饰", "本地生活", "二手商品", "奢侈品",
    "原料包装", "其他",
)

# The dedicated login window exposes a local-only Chrome DevTools endpoint.
# Export workers can attach to that exact window instead of trying to open the
# same user-data directory a second time (Chrome rejects that with
# ``Target page, context or browser has been closed``).
CHANMAMA_CDP_PORT = 19334


def resolve_chanmama_category(theme: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(theme.get("name") or ""),
            str(theme.get("description") or ""),
            str(theme.get("platform_category") or ""),
            *[str(value) for value in (theme.get("subcategories") or [])],
        ]
    )
    if any(word in text for word in ("保健", "滋补", "膳食营养")):
        return "医药保健"
    if any(word in text for word in ("鞋靴", "箱包")):
        return "鞋靴箱包"
    direct = next((category for category in CHANMAMA_CATEGORIES if category in text), "")
    if direct:
        return direct
    aliases = {
        "服饰鞋包": "服饰内衣",
        "女装": "服饰内衣",
        "男装": "服饰内衣",
        "内衣": "服饰内衣",
        "美妆": "美妆护肤",
        "家居生活": "家居家纺",
        "母婴": "母婴用品",
        "珠宝文玩": "珠宝饰品",
    }
    return next((category for keyword, category in aliases.items() if keyword in text), "全部")


def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return dict(DEFAULT_STATE)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return {**DEFAULT_STATE, **value}
    except (OSError, json.JSONDecodeError):
        return {**DEFAULT_STATE, "phase": "error", "message": "蝉妈妈状态文件无法读取"}


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**DEFAULT_STATE, **state, "updated_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


class ChanmamaManager:
    """启动独立Chrome进程；不复用也不检查用户日常浏览器的配置。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        # Chrome is launched directly by the local service.  Older versions
        # registered a custom URL protocol; on some Windows machines that
        # protocol opened an empty terminal window instead of Chrome.

    def _register_login_protocol(self) -> str:
        candidates = [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
            / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
            / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        chrome_path = next((path for path in candidates if path.is_file()), None)
        if chrome_path is None:
            raise RuntimeError("没有找到 Google Chrome，请先安装 Chrome")

        chrome_arguments = " ".join(
            [
                f'--user-data-dir="{self.settings.chanmama_profile_dir}"',
                "--remote-debugging-address=127.0.0.1",
                f"--remote-debugging-port={CHANMAMA_CDP_PORT}",
                "--new-window",
                f'"{self.settings.chanmama_start_url}"',
            ]
        )
        import winreg

        protocol = "liveagent-chanmama"
        protocol_root = rf"Software\Classes\{protocol}"
        command = f'"{chrome_path}" {chrome_arguments}'
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, protocol_root) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:LiveAgent Chanmama Browser")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, protocol_root + r"\shell\open\command"
        ) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
        return f"{protocol}://open"

    def _launch_login_chrome(self) -> None:
        candidates = [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
            / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
            / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        chrome_path = next((path for path in candidates if path.is_file()), None)
        if chrome_path is None:
            raise RuntimeError("没有找到 Google Chrome，请先安装 Chrome")
        self.settings.chanmama_profile_dir.mkdir(parents=True, exist_ok=True)
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._process = subprocess.Popen(
            [
                str(chrome_path),
                f"--user-data-dir={self.settings.chanmama_profile_dir}",
                "--remote-debugging-address=127.0.0.1",
                f"--remote-debugging-port={CHANMAMA_CDP_PORT}",
                "--new-window",
                self.settings.chanmama_start_url,
            ],
            cwd=str(chrome_path.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )

    def _finish_transient_operation(self, state: dict[str, Any], message: str) -> dict[str, Any]:
        """Return the UI to a real idle state after a worker/login action ends."""
        logged_in = bool(state.get("logged_in"))
        state.update(
            {
                "phase": "ready" if logged_in else "not_configured",
                "message": message,
                "busy": False,
                "mode": "",
                "pid": None,
                "page_url": "",
                "page_title": "",
            }
        )
        self.settings.chanmama_state_path.with_name("stop.request").unlink(missing_ok=True)
        write_state(self.settings.chanmama_state_path, state)
        return state

    def status(self) -> dict[str, Any]:
        state = read_state(self.settings.chanmama_state_path)
        # ``stopping`` is only a short-lived transition.  Older versions could
        # persist it forever (especially for the externally launched login
        # Chrome, which has no managed child process), making a fresh page load
        # look as if the user had already started an operation.  Reconcile that
        # stale state before exposing it to the UI.
        if state.get("phase") == "stopping" and self._process is None:
            state = self._finish_transient_operation(state, "尚未打开蝉妈妈专用浏览器")
        state["playwright_available"] = playwright_available()
        state["profile_dir"] = str(self.settings.chanmama_profile_dir)
        state["download_dir"] = str(self.settings.chanmama_download_dir)
        download_path = Path(str(state.get("download_path") or ""))
        if (
            state.get("capture_method") == "visible_web_table"
            and download_path.is_file()
            and not state.get("imported")
            and state.get("phase") == "error"
        ):
            state.update(
                {
                    "phase": "downloaded",
                    "message": "网页榜单已读取完成，正在导入候选池",
                    "busy": False,
                }
            )
            write_state(self.settings.chanmama_state_path, state)
        if self._process is not None and self._process.poll() is not None:
            self._process = None
            if state.get("busy"):
                if state.get("phase") == "stopping":
                    state = self._finish_transient_operation(state, "蝉妈妈操作已取消")
                else:
                    state.update({"busy": False, "phase": "error", "message": "蝉妈妈专用浏览器已退出，请重新尝试"})
                    write_state(self.settings.chanmama_state_path, state)
        return state

    def _start(
        self,
        mode: str,
        *,
        theme_id: int | None = None,
        category: str = "全部",
        period: str = "day",
    ) -> dict[str, Any]:
        if not playwright_available():
            raise RuntimeError("缺少Playwright，请先重新运行安装或检查命令")
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise RuntimeError("蝉妈妈专用浏览器正在运行，请先完成当前操作")
            stop_path = self.settings.chanmama_state_path.with_name("stop.request")
            stop_path.unlink(missing_ok=True)
            # The scout service itself runs without a console window, but the
            # Chanmama login worker must stay attached to the interactive
            # desktop so Playwright's headed Chrome is visible to the user.
            # Launching the worker with CREATE_NO_WINDOW caused Chrome to run
            # successfully in the background with no visible window.
            python_executable = Path(sys.executable)
            pythonw_executable = python_executable.with_name("pythonw.exe")
            worker_executable = (
                pythonw_executable if pythonw_executable.exists() else python_executable
            )
            command = [
                str(worker_executable),
                "-m",
                "live_scout_agent.chanmama_worker",
                mode,
                "--profile-dir",
                str(self.settings.chanmama_profile_dir),
                "--download-dir",
                str(self.settings.chanmama_download_dir),
                "--state-path",
                str(self.settings.chanmama_state_path),
                "--stop-path",
                str(stop_path),
                "--start-url",
                self.settings.chanmama_start_url,
            ]
            if theme_id is not None:
                command.extend(["--theme-id", str(theme_id)])
            command.extend(["--category", category, "--period", period])
            state = {
                "phase": "starting_login" if mode == "login" else "starting_export",
                "message": "正在打开蝉妈妈专用浏览器",
                "logged_in": bool(read_state(self.settings.chanmama_state_path).get("logged_in")),
                "busy": True,
                "mode": mode,
                "theme_id": theme_id,
                "category": category,
                "period": period,
                "download_path": "",
                "imported": False,
            }
            write_state(self.settings.chanmama_state_path, state)
            self._process = subprocess.Popen(
                command,
                cwd=self.settings.project_dir,
                creationflags=0,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            current = read_state(self.settings.chanmama_state_path)
            current["pid"] = self._process.pid
            write_state(self.settings.chanmama_state_path, current)
            return self.status()

    def start_login(self) -> dict[str, Any]:
        if os.name != "nt":
            return self._start("login")
        with self._lock:
            state = read_state(self.settings.chanmama_state_path)
            if state.get("busy"):
                raise RuntimeError("蝉妈妈专用浏览器正在运行，请先完成当前操作")
            self._launch_login_chrome()
            new_state = {
                "phase": "waiting_for_login",
                "message": (
                    "请在新打开的专用Chrome中登录蝉妈妈；登录完成后直接回到这里点击"
                    "“我已完成登录”。专用窗口可以保持打开，Agent更新榜单时会自动复用。"
                ),
                "logged_in": False,
                "busy": True,
                "mode": "external_login",
                "theme_id": None,
                "category": "全部",
                "period": "day",
                "download_path": "",
                "imported": False,
                "page_url": self.settings.chanmama_start_url,
                "page_title": "蝉妈妈专用登录窗口",
                "cdp_port": CHANMAMA_CDP_PORT,
                "launch_uri": "",
                "pid": self._process.pid if self._process else None,
            }
            write_state(self.settings.chanmama_state_path, new_state)
            return self.status()

    def complete_login(self) -> dict[str, Any]:
        state = read_state(self.settings.chanmama_state_path)
        if state.get("mode") == "external_login" and state.get("busy"):
            state.update(
                {
                    "phase": "ready",
                    "message": "蝉妈妈专用登录状态已保存",
                    "logged_in": True,
                    "busy": False,
                    "mode": "",
                }
            )
            write_state(self.settings.chanmama_state_path, state)
            return self.status()
        if state.get("mode") != "login" or not state.get("busy"):
            raise RuntimeError("当前没有等待确认的蝉妈妈登录窗口")
        self.settings.chanmama_state_path.with_name("stop.request").write_text("login-complete", encoding="utf-8")
        state.update({"phase": "finishing_login", "message": "正在保存蝉妈妈登录状态"})
        write_state(self.settings.chanmama_state_path, state)
        return self.status()

    def start_export(self, theme: dict[str, Any], period: str) -> dict[str, Any]:
        state = read_state(self.settings.chanmama_state_path)
        if not state.get("logged_in"):
            raise RuntimeError("请先完成蝉妈妈专用浏览器登录")
        if period not in {"day", "week", "month"}:
            raise RuntimeError("榜单周期只能是日榜、周榜或月榜")
        return self._start(
            "export",
            theme_id=int(theme["id"]),
            category=resolve_chanmama_category(theme),
            period=period,
        )

    def start_calibration(self) -> dict[str, Any]:
        state = read_state(self.settings.chanmama_state_path)
        if not state.get("logged_in"):
            raise RuntimeError("请先完成蝉妈妈专用浏览器登录")
        return self._start("calibrate")

    def stop(self) -> dict[str, Any]:
        state = read_state(self.settings.chanmama_state_path)
        if not state.get("busy"):
            return self.status()
        # Windows login uses an independently launched Chrome window rather
        # than a child worker.  There is nothing for the server to wait on, so
        # cancellation must immediately clear the busy flag.  The user may
        # close that dedicated Chrome window separately if it is still open.
        if state.get("mode") == "external_login":
            self._finish_transient_operation(state, "登录操作已取消；如专用Chrome仍打开，可直接关闭")
            return self.status()
        self.settings.chanmama_state_path.with_name("stop.request").write_text("stop", encoding="utf-8")
        state.update({"phase": "stopping", "message": "正在关闭蝉妈妈专用浏览器"})
        write_state(self.settings.chanmama_state_path, state)
        return self.status()
