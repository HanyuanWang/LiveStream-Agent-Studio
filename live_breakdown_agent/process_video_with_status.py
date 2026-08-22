from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = PROJECT_DIR / "workspace"
LOG_DIR = WORKSPACE_DIR / "logs"
STATUS_PATH = WORKSPACE_DIR / "current_status.json"
LATEST_LOG = LOG_DIR / "latest.log"


def popup(message: str, title: str = "直播拆解 Agent", icon: int = 0x40) -> None:
    if os.getenv("LIVE_AGENT_NO_POPUP") == "1":
        return
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, icon)
    except Exception:
        print(f"[提示] {message}")


def save_status(state: str, message: str, video: str = "", log_file: str = "") -> None:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": state,
        "message": message,
        "video": video,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "process_id": os.getpid(),
        "log_file": log_file,
    }
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_stem(path: Path) -> str:
    value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5_-]", "_", path.stem)
    return value[:40] or "video"


def run_and_stream(args: list[str], env: dict[str, str], log_path: Path) -> int:
    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            args,
            cwd=str(PROJECT_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        return process.wait()


def build_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_DIR / "src")
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ALIYUN_OSS_ENDPOINT"] = "https://oss-cn-beijing.aliyuncs.com"
    return env


def find_resumable_job(video: Path) -> Path | None:
    jobs_dir = WORKSPACE_DIR / "jobs"
    if not jobs_dir.exists():
        return None
    candidates: list[tuple[float, Path]] = []
    for state_path in jobs_dir.glob("*/state.json"):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            source = Path(str(state.get("source_video", ""))).resolve()
            stage = str(state.get("stage", ""))
            if source != video or stage == "excel_exported":
                continue
            job_dir = state_path.parent
            can_resume = (
                (job_dir / "transcript.json").exists()
                or (job_dir / "asr_raw.json").exists()
                or stage in {"audio_extracted", "transcription_submitted"}
            )
            if can_resume:
                candidates.append((state_path.stat().st_mtime, job_dir))
        except Exception:
            continue
    return max(candidates, default=(0.0, None), key=lambda item: item[0])[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", nargs="?")
    parser.add_argument("--missing-video", action="store_true")
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if args.missing_video or not args.video:
        save_status("not_started", "没有收到视频路径")
        popup(
            "没有收到视频文件。\n\n正确方法：关闭黑框，把视频文件拖到“03_处理直播视频.cmd”的图标上。",
            icon=0x30,
        )
        return 1

    video = Path(args.video).resolve()
    run_log: Path | None = None
    try:
        if not video.is_file():
            raise FileNotFoundError(f"没有找到视频文件：{video}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_log = LOG_DIR / f"{timestamp}_{safe_stem(video)}.log"
        size_gb = video.stat().st_size / (1024 ** 3)
        run_log.write_text(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 收到视频：{video}\n文件大小：{size_gb:.2f} GB\n",
            encoding="utf-8",
        )
        shutil.copyfile(run_log, LATEST_LOG)
        print(f"[已收到] {video}", flush=True)
        print(f"[文件大小] {size_gb:.2f} GB", flush=True)
        save_status("starting", "已收到视频，正在检查配置", str(video), str(run_log))

        env = build_environment()
        doctor_code = run_and_stream(
            [sys.executable, "-m", "live_breakdown_agent.cli", "doctor"], env, run_log
        )
        shutil.copyfile(run_log, LATEST_LOG)
        if doctor_code != 0:
            raise RuntimeError(f"本地配置检查失败，错误码 {doctor_code}")

        if os.getenv("LIVE_AGENT_DIAGNOSTIC_ONLY") == "1":
            with run_log.open("a", encoding="utf-8") as log:
                log.write("诊断通过：拖入参数、文件路径和本地配置均正常；未调用云端服务。\n")
            shutil.copyfile(run_log, LATEST_LOG)
            save_status(
                "diagnostic_ok",
                "拖入参数、视频文件和本地配置均正常；未调用云端服务",
                str(video),
                str(run_log),
            )
            print("[诊断通过] 未调用云端服务。", flush=True)
            return 0

        resumable_job = find_resumable_job(video)
        action_message = (
            "检测到未完成任务，正在从断点继续；不会重新上传或重复提交转写"
            if resumable_job
            else "正在提取音频、上传、转写和分析；请不要关闭黑框"
        )
        save_status(
            "running",
            action_message,
            str(video),
            str(run_log),
        )
        popup(
            f"已经开始处理：\n{video.name}\n\n{action_message}\n完成或失败后会再次弹窗。"
        )
        print("[正在处理] 请不要关闭本窗口。长视频可能需要较长时间。", flush=True)

        agent_args = [sys.executable, "-m", "live_breakdown_agent.cli"]
        if resumable_job:
            print(f"[断点续跑] {resumable_job}", flush=True)
            agent_args.extend(["resume-job", str(resumable_job)])
        else:
            agent_args.extend(["run", str(video)])
        agent_code = run_and_stream(
            agent_args,
            env,
            run_log,
        )
        shutil.copyfile(run_log, LATEST_LOG)
        if agent_code != 0:
            raise RuntimeError(f"处理程序退出，错误码 {agent_code}")

        output_dir = WORKSPACE_DIR / "output"
        outputs = sorted(output_dir.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
        output_text = str(outputs[0]) if outputs else str(output_dir)
        save_status("completed", "处理完成", str(video), str(run_log))
        popup(f"处理完成。\n\n结果位置：\n{output_text}")
        return 0
    except Exception as exc:
        error_text = str(exc)
        try:
            with LATEST_LOG.open("a", encoding="utf-8") as log:
                log.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ERROR: {error_text}\n")
        except Exception:
            pass
        save_status("failed", error_text, str(video), str(run_log or LATEST_LOG))
        print(f"[处理失败] {error_text}", file=sys.stderr, flush=True)
        popup(f"处理失败：\n{error_text}\n\n错误日志：\n{LATEST_LOG}", icon=0x10)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
