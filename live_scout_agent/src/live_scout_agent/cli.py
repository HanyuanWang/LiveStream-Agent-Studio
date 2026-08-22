from __future__ import annotations

import argparse
import json
import os
import threading
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from .config import Settings
from .database import Database
from .chanmama import playwright_available
from .server import serve


def existing_server_is_ready(host: str, port: int) -> bool:
    try:
        with urlopen(f"http://{host}:{port}/api/status", timeout=1.2) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(prog="live-scout", description="直播主播发现 Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    start = subparsers.add_parser("start", help="启动本地控制台")
    start.add_argument("--no-browser", action="store_true")
    subparsers.add_parser("doctor", help="检查运行环境")
    args = parser.parse_args()
    settings = Settings.load()
    if args.command == "doctor":
        Database(settings.database_path)
        chrome_candidates = [
            Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        ]
        result = {
            "python": "OK",
            "database": "OK",
            "web_files": "OK" if (settings.web_dir / "index.html").exists() else "MISSING",
            "playwright": "OK" if playwright_available() else "MISSING",
            "chrome": "FOUND" if any(path.exists() for path in chrome_candidates) else "MISSING",
            "qwen": "SET" if settings.dashscope_api_key else "MISSING",
            "quick_recorder": "FOUND" if settings.quick_recorder_exe.exists() else "MISSING",
            "breakdown_agent": "FOUND" if settings.breakdown_project_dir.exists() else "MISSING",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if existing_server_is_ready(settings.host, settings.port):
        if not args.no_browser:
            webbrowser.open(f"http://{settings.host}:{settings.port}")
        print(f"Agent 已经在运行：http://{settings.host}:{settings.port}")
        return
    if not args.no_browser:
        def open_browser() -> None:
            time.sleep(1.1)
            webbrowser.open(f"http://{settings.host}:{settings.port}")
        threading.Thread(target=open_browser, daemon=True).start()
    serve(settings)


if __name__ == "__main__":
    main()
