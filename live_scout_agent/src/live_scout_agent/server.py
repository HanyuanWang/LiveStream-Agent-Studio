from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import traceback
import urllib.parse
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .config import Settings
from .database import Database
from .domain_parser import parse_theme_rules, parse_theme_with_qwen
from .chanmama import ChanmamaManager, write_state
from .creator_reports import CreatorReportManager
from .importers import parse_leaderboard
from .recorder import (
    add_candidates_to_quick,
    launch_quick_recorder,
    resolve_douyin_profile_urls,
    start_quick_monitor,
    stop_quick_monitor,
    write_quick_import_file,
)
from .scoring import score_candidates


PROCESS_STARTED_AT = datetime.now().astimezone().isoformat(timespec="seconds")
REPORT_ENGINE_VERSION = "2026-07-31-full-detail-v2"


def normalize_douyin_profile_url(value: str) -> str:
    """Extract and validate a Douyin profile/share URL from pasted text."""
    match = re.search(r"https?://[^\s]+", str(value or "").strip(), re.IGNORECASE)
    if not match:
        raise ValueError("没有识别到抖音主页链接，请粘贴以 http:// 或 https:// 开头的链接")
    raw_url = match.group(0).rstrip("，。；;、）》】]})>\"'")
    parsed = urllib.parse.urlparse(raw_url)
    hostname = (parsed.hostname or "").lower()
    if not (hostname == "douyin.com" or hostname.endswith(".douyin.com")):
        raise ValueError("目前只支持 douyin.com 的主播主页或抖音分享链接")
    if not parsed.path or parsed.path == "/":
        raise ValueError("链接中没有主播主页路径，请重新复制主播主页链接")
    return urllib.parse.urlunparse(
        ("https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", "")
    )


class ScoutApplication:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings.database_path)
        self.chanmama = ChanmamaManager(settings)
        self.creator_reports = CreatorReportManager(settings, self.db)

    def recorder_status(self) -> dict[str, Any]:
        candidates = self.db.list_auto_breakdown_candidates()
        recorder = self.settings.current_quick_recorder_exe()
        return {
            "configured": bool(recorder),
            "found": bool(recorder and recorder.is_file()),
            "path": str(recorder) if recorder else "",
            "enabled_candidates": len(candidates),
            "enabled_candidate_details": [
                {
                    "id": candidate.get("id"),
                    "anchor_name": candidate.get("anchor_name", ""),
                    "douyin_id": candidate.get("douyin_id", ""),
                    "profile_url": candidate.get("profile_url", ""),
                    "theme_name": candidate.get("theme_name", ""),
                    "status": candidate.get("status", ""),
                }
                for candidate in candidates
            ],
        }

    def parse_theme(self, description: str) -> dict[str, Any]:
        try:
            return parse_theme_with_qwen(
                description,
                self.settings.dashscope_api_key,
                self.settings.dashscope_base_url,
                self.settings.text_model,
            ).to_dict()
        except Exception as exc:
            draft = parse_theme_rules(description).to_dict()
            draft["parser_warning"] = f"AI解析暂时不可用，已使用本地规则：{exc}"
            return draft

    def import_file(self, data: dict[str, Any]) -> dict[str, Any]:
        theme_id = int(data["theme_id"])
        file_name = str(data["file_name"])
        content = base64.b64decode(data["content_base64"], validate=True)
        return self.import_content(theme_id, file_name, content, str(data.get("source") or "其他"))

    def import_profile_link(self, data: dict[str, Any]) -> dict[str, Any]:
        theme_id = int(data.get("theme_id") or 0)
        theme = self.db.get_theme(theme_id)
        if not theme:
            raise ValueError("请先选择关注领域")
        anchor_name = str(data.get("anchor_name") or "").strip()
        if len(anchor_name) < 1:
            raise ValueError("请填写主播名称；它将用于匹配快抖生成的录像文件夹")
        if len(anchor_name) > 80:
            raise ValueError("主播名称不能超过80个字符")
        profile_url = normalize_douyin_profile_url(str(data.get("profile_url") or ""))
        source = "用户手动导入"
        import_id = self.db.create_import(
            theme_id,
            "抖音主页链接",
            source,
            1,
            0,
            [],
        )
        imported = self.db.upsert_candidates(
            theme_id,
            import_id,
            source,
            [
                {
                    "source_key": profile_url,
                    "anchor_name": anchor_name,
                    "profile_url": profile_url,
                    "category": str(theme.get("platform_category") or ""),
                    "score": 0,
                    "status": "candidate",
                    "reasons": ["用户通过抖音主页链接手动导入"],
                    "raw_data": {
                        "主播": anchor_name,
                        "抖音主页": profile_url,
                        "导入方式": source,
                    },
                }
            ],
        )
        with self.db.connect() as db:
            db.execute(
                "UPDATE imports SET imported_count=? WHERE id=?",
                (imported, import_id),
            )
        candidate = next(
            (
                item
                for item in self.db.list_candidates(theme_id=theme_id, limit=5000)
                if item.get("source") == source and item.get("source_key") == profile_url
            ),
            None,
        )
        return {"imported": imported, "candidate": candidate}

    def import_content(self, theme_id: int, file_name: str, content: bytes, source: str) -> dict[str, Any]:
        theme = self.db.get_theme(theme_id)
        if not theme:
            raise ValueError("关注领域不存在")
        if len(content) > 30 * 1024 * 1024:
            raise ValueError("榜单文件不能超过30MB")
        upload_path = self.settings.workspace_dir / "uploads" / Path(file_name).name
        upload_path.write_bytes(content)
        candidates, warnings = parse_leaderboard(file_name, content)
        if source == "蝉妈妈":
            link_path = self.settings.chanmama_state_path.with_name("leaderboard_links.json")
            if link_path.exists():
                try:
                    link_map = json.loads(link_path.read_text(encoding="utf-8"))
                    for candidate in candidates:
                        if not candidate.get("analysis_url"):
                            candidate["analysis_url"] = str(link_map.get(candidate["anchor_name"]) or "")
                except (OSError, json.JSONDecodeError):
                    warnings.append("达人详情页链接映射读取失败，后续报告将仅使用榜单字段")
        scored = score_candidates(candidates, theme)
        import_id = self.db.create_import(theme_id, file_name, source, len(candidates), 0, warnings)
        imported = self.db.upsert_candidates(theme_id, import_id, source, scored)
        with self.db.connect() as db:
            db.execute("UPDATE imports SET imported_count=? WHERE id=?", (imported, import_id))
        return {"import_id": import_id, "row_count": len(candidates), "imported_count": imported, "warnings": warnings}

    def chanmama_status(self) -> dict[str, Any]:
        state = self.chanmama.status()
        download_path = str(state.get("download_path") or "")
        if state.get("phase") == "downloaded" and download_path and not state.get("imported"):
            path = Path(download_path)
            if not path.exists():
                state.update({"phase": "error", "message": "蝉妈妈下载文件不存在", "busy": False})
                write_state(self.settings.chanmama_state_path, state)
            else:
                try:
                    result = self.import_content(int(state["theme_id"]), path.name, path.read_bytes(), "蝉妈妈")
                    state.update(
                        {
                            "phase": "imported",
                            "message": f"蝉妈妈榜单已导入，更新{result['imported_count']}位主播",
                            "busy": False,
                            "imported": True,
                            "import_result": result,
                        }
                    )
                    write_state(self.settings.chanmama_state_path, state)
                except Exception as exc:
                    state.update({"phase": "error", "message": f"榜单下载成功，但自动导入失败：{exc}", "busy": False})
                    write_state(self.settings.chanmama_state_path, state)
        return self.chanmama.status()


def make_handler(app: ScoutApplication):
    class Handler(BaseHTTPRequestHandler):
        server_version = "LiveScout/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _error(self, exc: Exception, status: int = 400) -> None:
            self._json({"error": str(exc)}, status)

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 45 * 1024 * 1024:
                raise ValueError("请求过大")
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8"))

        def _serve_static(self, relative: str) -> None:
            relative = relative or "index.html"
            path = (app.settings.web_dir / relative).resolve()
            if app.settings.web_dir.resolve() not in path.parents and path != app.settings.web_dir.resolve():
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not path.exists() or not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content = path.read_bytes()
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") or mime.endswith("javascript") else ""))
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            try:
                if parsed.path == "/api/status":
                    recorder = app.settings.current_quick_recorder_exe()
                    self._json(
                        {
                            "process_id": os.getpid(),
                            "process_started_at": PROCESS_STARTED_AT,
                            "report_engine_version": REPORT_ENGINE_VERSION,
                            "dashboard": app.db.dashboard(),
                            "ai_configured": bool(app.settings.dashscope_api_key),
                            "quick_recorder_found": bool(recorder and recorder.is_file()),
                            "quick_recorder_path": str(recorder) if recorder else "",
                            "breakdown_agent_found": app.settings.breakdown_project_dir.exists(),
                        }
                    )
                elif parsed.path == "/api/themes":
                    self._json({"themes": app.db.list_themes()})
                elif parsed.path == "/api/chanmama/status":
                    self._json(app.chanmama_status())
                elif parsed.path == "/api/reports/status":
                    self._json(app.creator_reports.status())
                elif parsed.path == "/api/recorder/status":
                    self._json(app.recorder_status())
                elif parsed.path == "/api/candidates":
                    theme_id = int(query["theme_id"][0]) if query.get("theme_id") else None
                    status = query.get("status", [""])[0]
                    self._json({"candidates": app.db.list_candidates(theme_id, status)})
                elif parsed.path.startswith("/downloads/"):
                    name = Path(urllib.parse.unquote(parsed.path.removeprefix("/downloads/"))).name
                    path = app.settings.workspace_dir / "exports" / name
                    if not path.exists():
                        self.send_error(404)
                        return
                    content = path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(path.name)}")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                elif parsed.path.startswith("/reports/"):
                    encoded_name = parsed.path.removeprefix("/reports/")
                    decoded_name = urllib.parse.unquote(encoded_name)
                    # Compatibility for report links produced by older pages,
                    # which URL-encoded an already encoded download path.
                    if "%" in decoded_name:
                        decoded_name = urllib.parse.unquote(decoded_name)
                    name = Path(decoded_name).name
                    path = app.settings.report_dir / name
                    if not path.exists():
                        self.send_error(404)
                        return
                    content = path.read_bytes()
                    self.send_response(200)
                    content_type = (
                        "application/json; charset=utf-8"
                        if path.suffix.lower() == ".json"
                        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(path.name)}")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                elif parsed.path.startswith("/breakdowns/"):
                    job_id_text = parsed.path.removeprefix("/breakdowns/").strip("/")
                    if not job_id_text.isdigit():
                        self.send_error(404)
                        return
                    job = app.db.get_integration_job(int(job_id_text))
                    output_path = Path(
                        str(((job or {}).get("payload") or {}).get("output_path") or "")
                    )
                    if (
                        not job
                        or job.get("kind") != JOB_KIND
                        or job.get("status") != "completed"
                        or output_path.suffix.lower() != ".xlsx"
                        or not output_path.exists()
                    ):
                        self.send_error(404)
                        return
                    content = output_path.read_bytes()
                    self.send_response(200)
                    self.send_header(
                        "Content-Type",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                    self.send_header(
                        "Content-Disposition",
                        f"attachment; filename*=UTF-8''{urllib.parse.quote(output_path.name)}",
                    )
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                elif parsed.path.startswith("/api/"):
                    self.send_error(404)
                else:
                    self._serve_static(parsed.path.lstrip("/") or "index.html")
            except Exception as exc:
                self._error(exc)

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            try:
                data = self._body()
                if parsed.path == "/api/themes/parse":
                    description = str(data.get("description") or "").strip()
                    if len(description) < 4:
                        raise ValueError("请至少写一句对关注领域的描述")
                    self._json({"theme": app.parse_theme(description)})
                elif parsed.path == "/api/themes":
                    self._json({"theme": app.db.create_theme(data)}, 201)
                elif parsed.path == "/api/imports":
                    self._json(app.import_file(data), 201)
                elif parsed.path == "/api/candidates/manual":
                    self._json(app.import_profile_link(data), 201)
                elif parsed.path == "/api/chanmama/login/start":
                    self._json(app.chanmama.start_login())
                elif parsed.path == "/api/chanmama/login/complete":
                    self._json(app.chanmama.complete_login())
                elif parsed.path == "/api/chanmama/calibrate/start":
                    self._json(app.chanmama.start_calibration())
                elif parsed.path == "/api/chanmama/export/start":
                    theme_id = int(data.get("theme_id") or 0)
                    theme = app.db.get_theme(theme_id)
                    if not theme:
                        raise ValueError("请先选择关注领域")
                    self._json(app.chanmama.start_export(theme, str(data.get("period") or "day")))
                elif parsed.path == "/api/chanmama/stop":
                    self._json(app.chanmama.stop())
                elif parsed.path == "/api/reports/generate":
                    if app.chanmama.status().get("busy"):
                        raise RuntimeError("蝉妈妈专用浏览器正在执行其他任务，请稍后再生成拆解报告")
                    ids = [int(value) for value in data.get("candidate_ids", [])]
                    self._json(app.creator_reports.start(ids))
                elif parsed.path == "/api/candidates/status":
                    count = app.db.update_candidate_status([int(value) for value in data.get("candidate_ids", [])], str(data.get("status")))
                    self._json({"updated": count})
                elif parsed.path == "/api/recorder/export":
                    ids = [int(value) for value in data.get("candidate_ids", [])]
                    all_candidates = app.db.list_candidates(limit=5000)
                    selected = [candidate for candidate in all_candidates if candidate["id"] in ids]
                    if not selected:
                        raise ValueError("请先选择主播")
                    theme_name = selected[0].get("theme_name", "主播")
                    path, missing = write_quick_import_file(selected, app.settings.workspace_dir / "exports", theme_name)
                    self._json({"file_name": path.name, "download_url": "/downloads/" + urllib.parse.quote(path.name), "link_count": len(selected) - len(missing), "missing_profiles": missing})
                elif parsed.path == "/api/recorder/launch":
                    recorder = app.settings.current_quick_recorder_exe()
                    if not recorder:
                        raise FileNotFoundError("尚未配置录制助手；请在 LiveAgent Studio 的设置与连接页面粘贴 EXE 完整路径")
                    launch_quick_recorder(recorder)
                    self._json({"launched": True})
                elif parsed.path == "/api/recorder/add":
                    ids = [int(value) for value in data.get("candidate_ids", [])]
                    all_candidates = app.db.list_candidates(limit=5000)
                    selected = [candidate for candidate in all_candidates if candidate["id"] in ids]
                    if not selected:
                        raise ValueError("请先选择主播")
                    chanmama_state = app.chanmama.status()
                    if chanmama_state.get("busy"):
                        raise RuntimeError("蝉妈妈专用浏览器正在执行其他任务，请稍后再加入快抖")
                    resolved = resolve_douyin_profile_urls(
                        selected,
                        app.settings.chanmama_profile_dir,
                    )
                    app.db.update_candidate_profile_urls(resolved)
                    recorder = app.settings.current_quick_recorder_exe()
                    if not recorder:
                        raise FileNotFoundError("尚未配置录制助手；请在 LiveAgent Studio 的设置与连接页面粘贴 EXE 完整路径")
                    added_ids, missing = add_candidates_to_quick(selected, recorder)
                    if added_ids:
                        app.db.update_candidate_status(added_ids, "monitoring")
                        app.db.set_candidate_auto_breakdown(added_ids, True)
                    self._json(
                        {
                            "added": len(added_ids),
                            "resolved_profiles": len(resolved),
                            "missing_profiles": missing,
                        }
                    )
                elif parsed.path == "/api/recorder/start-monitor":
                    recorder = app.settings.current_quick_recorder_exe()
                    if not recorder:
                        raise FileNotFoundError("尚未配置录制助手；请在 LiveAgent Studio 的设置与连接页面粘贴 EXE 完整路径")
                    start_quick_monitor(recorder)
                    self._json({"started": True})
                elif parsed.path == "/api/recorder/stop-monitor":
                    recorder = app.settings.current_quick_recorder_exe()
                    if not recorder:
                        raise FileNotFoundError("尚未配置录制助手；请在 LiveAgent Studio 的设置与连接页面粘贴 EXE 完整路径")
                    stop_quick_monitor(recorder)
                    self._json({"stopped": True})
                else:
                    self.send_error(404)
            except Exception as exc:
                traceback.print_exc()
                self._error(exc)

        def do_DELETE(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            try:
                if parsed.path.startswith("/api/themes/"):
                    theme_id_text = parsed.path.removeprefix("/api/themes/").strip("/")
                    if not theme_id_text.isdigit():
                        raise ValueError("关注领域编号无效")
                    theme_id = int(theme_id_text)
                    chanmama_state = app.chanmama.status()
                    if (
                        chanmama_state.get("busy")
                        and int(chanmama_state.get("theme_id") or 0) == theme_id
                    ):
                        raise RuntimeError("该领域正在读取蝉妈妈榜单，请完成或取消当前任务后再删除")
                    self._json(app.db.delete_theme(theme_id))
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
            except Exception as exc:
                traceback.print_exc()
                self._error(exc)

    return Handler


def serve(settings: Settings) -> None:
    app = ScoutApplication(settings)
    server = ThreadingHTTPServer((settings.host, settings.port), make_handler(app))
    print(f"直播主播发现 Agent 已启动：http://{settings.host}:{settings.port}")
    print("关闭本窗口会停止 Agent。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
