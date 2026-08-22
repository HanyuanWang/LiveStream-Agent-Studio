from __future__ import annotations

import cgi
import json
import mimetypes
import re
import shutil
import threading
import traceback
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .config import Settings
from .pipeline import process_job

SETTINGS = Settings.load()
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


def safe_filename(name: str) -> str:
    name = Path(name or "upload.bin").name
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)


def save_state(job_id: str) -> None:
    state = JOBS[job_id].copy()
    (SETTINGS.workspace / "jobs" / job_id / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def update(job_id: str, **changes) -> None:
    with LOCK:
        state = JOBS[job_id]
        state.update(changes)
        if "message" in changes:
            state.setdefault("log", []).append(f"[{datetime.now():%H:%M:%S}] {changes['message']}")
            state["log"] = state["log"][-60:]
        save_state(job_id)


def worker(job_id: str, inputs: dict[str, Path], options: dict) -> None:
    try:
        update(job_id, status="running", status_text="处理中", progress=5, message="资料已接收，开始读取")
        result = process_job(Path(JOBS[job_id]["job_dir"]), inputs, options, SETTINGS, lambda p, m: update(job_id, progress=p, message=m))
        output_items = []
        for item in result["outputs"]:
            path = Path(item["path"])
            output_items.append({"label": item["label"], "url": f"/api/jobs/{job_id}/files/{path.name}"})
        update(job_id, status="completed", status_text="已完成", progress=100, message="Excel、Word 和处理说明均已生成", outputs=output_items, summary=result["summary"])
    except Exception as exc:
        job_dir = Path(JOBS[job_id]["job_dir"])
        (job_dir / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
        update(job_id, status="failed", status_text="处理失败", message=f"{exc}（详细日志：{job_dir / 'error.log'}）")


class Handler(BaseHTTPRequestHandler):
    server_version = "LiveRetroAgent/0.1"

    def log_message(self, fmt, *args):
        return

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)

    def send_file(self, path: Path, download=False):
        if not path.exists() or not path.is_file():
            self.send_error(404); return
        body = path.read_bytes(); content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body)))
        if download:
            encoded = ''.join(f'%{b:02X}' for b in path.name.encode('utf-8'))
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded}")
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path); path = unquote(parsed.path)
        if path == "/api/health":
            self.send_json({"ok": True, "model_ready": bool(SETTINGS.dashscope_key), "port": SETTINGS.port}); return
        match = re.fullmatch(r"/api/jobs/([a-zA-Z0-9_-]+)", path)
        if match:
            state = JOBS.get(match.group(1))
            if not state:
                state_path = SETTINGS.workspace / "jobs" / match.group(1) / "state.json"
                if state_path.exists(): state = json.loads(state_path.read_text(encoding="utf-8"))
            self.send_json(state or {"error": "任务不存在"}, 200 if state else 404); return
        match = re.fullmatch(r"/api/jobs/([a-zA-Z0-9_-]+)/files/(.+)", path)
        if match:
            job_id, filename = match.groups(); output_dir = (SETTINGS.workspace / "jobs" / job_id / "output").resolve(); target = (output_dir / Path(filename).name).resolve()
            if output_dir not in target.parents: self.send_error(403); return
            self.send_file(target, download=True); return
        static = SETTINGS.project_dir / "web" / ("index.html" if path == "/" else path.lstrip("/"))
        if static.exists() and static.is_file(): self.send_file(static); return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/jobs":
            self.send_error(404); return
        try:
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", ""), "CONTENT_LENGTH": self.headers.get("Content-Length", "0")})
            breakdown = form["breakdown"] if "breakdown" in form else None
            if breakdown is None or not getattr(breakdown, "filename", ""):
                self.send_json({"error": "请上传逐字稿拆解 Excel"}, 400); return
            job_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
            job_dir = SETTINGS.workspace / "jobs" / job_id; input_dir = job_dir / "input"; input_dir.mkdir(parents=True, exist_ok=True)
            inputs: dict[str, Path] = {}
            for role in ("breakdown", "orders", "minute", "session"):
                item = form[role] if role in form else None
                if item is None or not getattr(item, "filename", ""): continue
                target = input_dir / f"{role}_{safe_filename(item.filename)}"
                with target.open("wb") as handle: shutil.copyfileobj(item.file, handle)
                inputs[role] = target
            def field(name):
                item = form[name] if name in form else None
                return item.value.strip() if item is not None and getattr(item, "value", None) else ""
            options = {"official_gmv": field("official_gmv"), "live_start": field("live_start"), "session_name": field("session_name")}
            state = {"job_id": job_id, "job_dir": str(job_dir), "status": "queued", "status_text": "排队中", "progress": 2, "message": "等待处理", "log": [], "outputs": []}
            with LOCK: JOBS[job_id] = state; save_state(job_id)
            threading.Thread(target=worker, args=(job_id, inputs, options), daemon=True).start()
            self.send_json({"job_id": job_id}, 201)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)


def serve() -> None:
    SETTINGS.workspace.mkdir(parents=True, exist_ok=True); (SETTINGS.workspace / "jobs").mkdir(parents=True, exist_ok=True); (SETTINGS.workspace / "output").mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", SETTINGS.port), Handler)
    print(f"直播复盘 Agent 已启动：http://127.0.0.1:{SETTINGS.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    serve()

