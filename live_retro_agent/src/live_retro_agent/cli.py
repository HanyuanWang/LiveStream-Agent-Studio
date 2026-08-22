from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

from .config import Settings
from .pipeline import process_job


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def start(settings: Settings) -> int:
    url = f"http://127.0.0.1:{settings.port}/"
    if not port_open(settings.port):
        service = settings.workspace / "service"; service.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S"); stdout = (service / f"server_{stamp}.out.log").open("w", encoding="utf-8"); stderr = (service / f"server_{stamp}.err.log").open("w", encoding="utf-8")
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        proc = subprocess.Popen([sys.executable, "-m", "live_retro_agent.server"], cwd=settings.project_dir, stdout=stdout, stderr=stderr, creationflags=flags, close_fds=True)
        (service / "server.pid").write_text(str(proc.pid), encoding="ascii")
        for _ in range(40):
            if port_open(settings.port): break
            time.sleep(.25)
        if not port_open(settings.port):
            print(f"启动失败，请查看 {service}"); return 2
    webbrowser.open(url); print(f"已打开 {url}"); return 0


def stop(settings: Settings) -> int:
    pid_path = settings.workspace / "service" / "server.pid"
    if not pid_path.exists(): print("没有找到运行中的服务记录。"); return 0
    pid = pid_path.read_text(encoding="ascii").strip()
    subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True)
    pid_path.unlink(missing_ok=True); print("直播复盘 Agent 已停止。"); return 0


def doctor(settings: Settings) -> int:
    checks = {"Python": Path(sys.executable).exists(), "网页文件": (settings.project_dir / "web" / "index.html").exists(), "Excel生成组件": True, "大模型API Key": bool(settings.dashscope_key), "服务运行": port_open(settings.port)}
    print("直播复盘 Agent 配置检查\n" + "=" * 36)
    for name, ok in checks.items(): print(f"{'[正常]' if ok else '[需要处理]'} {name}")
    print(f"\n网页地址：http://127.0.0.1:{settings.port}/")
    return 0 if all(v for k,v in checks.items() if k != "服务运行") else 2


def run_once(args, settings: Settings) -> int:
    job_id = datetime.now().strftime("manual_%Y%m%d_%H%M%S"); job_dir = settings.workspace / "jobs" / job_id; input_dir = job_dir / "input"; input_dir.mkdir(parents=True, exist_ok=True)
    inputs = {}
    for role in ("breakdown", "orders", "minute", "session"):
        value = getattr(args, role, None)
        if value: inputs[role] = Path(value).resolve()
    result = process_job(job_dir, inputs, {"official_gmv": args.official_gmv, "live_start": args.live_start, "session_name": args.session_name}, settings, lambda p,m: print(f"[{p:3}%] {m}", flush=True))
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="command")
    for name in ("start","stop","doctor"): sub.add_parser(name)
    run=sub.add_parser("process"); run.add_argument("--breakdown",required=True); run.add_argument("--orders"); run.add_argument("--minute"); run.add_argument("--session"); run.add_argument("--official-gmv",dest="official_gmv"); run.add_argument("--live-start",dest="live_start",default=""); run.add_argument("--session-name",dest="session_name",default="")
    args=parser.parse_args(argv); settings=Settings.load(); command=args.command or "start"
    if command=="start": return start(settings)
    if command=="stop": return stop(settings)
    if command=="doctor": return doctor(settings)
    if command=="process": return run_once(args,settings)
    return 2


if __name__ == "__main__": raise SystemExit(main())
