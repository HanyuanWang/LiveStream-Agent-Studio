from __future__ import annotations

import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from .chanmama import CHANMAMA_CDP_PORT


def write_quick_import_file(
    candidates: list[dict[str, Any]],
    export_dir: Path,
    theme_name: str,
) -> tuple[Path, list[str]]:
    export_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(
        character for character in theme_name if character not in '<>:"/\\|?*'
    ).strip() or "主播"
    path = export_dir / f"{safe_name}_待加入快抖.txt"
    links = list(
        dict.fromkeys(
            str(candidate.get("profile_url") or "").strip()
            for candidate in candidates
            if candidate.get("profile_url")
        )
    )
    missing = [
        candidate.get("anchor_name", "未知主播")
        for candidate in candidates
        if not candidate.get("profile_url")
    ]
    path.write_text("\n".join(links), encoding="utf-8-sig")
    return path, missing


def launch_quick_recorder(executable: Path) -> None:
    if not executable.exists():
        raise FileNotFoundError(f"没有找到快抖直播录制助手：{executable}")
    subprocess.Popen([str(executable)], cwd=str(executable.parent))


def _invoke_protocol(executable: Path, uri: str) -> None:
    if not executable.exists():
        raise FileNotFoundError(f"没有找到快抖直播录制助手：{executable}")
    # 快抖单实例程序会把第二个进程的 kdlive:// 命令转交给已运行主进程。
    subprocess.Popen([str(executable), uri], cwd=str(executable.parent))


def resolve_douyin_profile_urls(
    candidates: list[dict[str, Any]],
    chanmama_profile_dir: Path,
) -> dict[int, str]:
    pending = [
        candidate
        for candidate in candidates
        if not str(candidate.get("profile_url") or "").strip()
        and str(candidate.get("analysis_url") or "").strip()
    ]
    if not pending:
        return {}
    resolved: dict[int, str] = {}
    with sync_playwright() as playwright:
        attached_browser = None
        context = None
        owns_context = False
        page = None
        try:
            # The login Chrome owns the persistent profile.  Reuse it through
            # the loopback CDP endpoint instead of launching a second Chrome
            # with the same profile, which Chrome immediately terminates.
            try:
                attached_browser = playwright.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{CHANMAMA_CDP_PORT}", timeout=10_000
                )
                if attached_browser.contexts:
                    context = attached_browser.contexts[0]
            except Exception:
                attached_browser = None
            if context is None:
                try:
                    context = playwright.chromium.launch_persistent_context(
                        str(chanmama_profile_dir),
                        channel="chrome",
                        headless=True,
                        no_viewport=True,
                        args=["--disable-background-timer-throttling"],
                    )
                    owns_context = True
                except Exception as exc:
                    if "Target page, context or browser has been closed" in str(exc):
                        raise RuntimeError(
                            "无法连接蝉妈妈专用Chrome。请先点击“打开专用浏览器登录”，"
                            "保持该窗口打开，再点击“自动加入快抖”。"
                        ) from exc
                    raise
            page = context.new_page()
            for candidate in pending:
                detail_url = urljoin(
                    "https://www.chanmama.com/",
                    str(candidate.get("analysis_url") or ""),
                )
                try:
                    page.goto(detail_url, wait_until="domcontentloaded", timeout=60_000)
                    page.wait_for_timeout(2_500)
                    links = page.locator("a[href*='douyin.com/user/']")
                    profile_url = ""
                    for index in range(links.count()):
                        link = links.nth(index)
                        profile_url = str(link.get_attribute("href") or "").strip()
                        parsed = urllib.parse.urlparse(profile_url)
                        if (
                            parsed.scheme in {"http", "https"}
                            and parsed.netloc.endswith("douyin.com")
                            and parsed.path.startswith("/user/")
                        ):
                            break
                        profile_url = ""
                    if profile_url:
                        candidate["profile_url"] = profile_url
                        resolved[int(candidate["id"])] = profile_url
                except Exception:
                    continue
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            if owns_context and context is not None:
                context.close()
    return resolved


def add_candidates_to_quick(
    candidates: list[dict[str, Any]],
    executable: Path,
) -> tuple[list[int], list[str]]:
    added_ids: list[int] = []
    missing: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = str(candidate.get("profile_url") or "").strip()
        if not url:
            missing.append(str(candidate.get("anchor_name") or "未知主播"))
            continue
        if url in seen:
            continue
        seen.add(url)
        encoded = urllib.parse.quote(url, safe="")
        _invoke_protocol(executable, f"kdlive://add?url={encoded}")
        added_ids.append(int(candidate["id"]))
        time.sleep(0.45)
    return added_ids, missing


def start_quick_monitor(executable: Path) -> None:
    _invoke_protocol(executable, "kdlive://start-monitor")


def stop_quick_monitor(executable: Path) -> None:
    _invoke_protocol(executable, "kdlive://stop-monitor")
