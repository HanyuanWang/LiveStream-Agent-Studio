from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .database import Database


JOB_KIND = "recording_breakdown"
VIDEO_EXTENSIONS = {".mp4", ".ts", ".flv", ".mkv", ".mov"}
ACTIVE_STATUSES = {
    "queued",
    "starting",
    "checking",
    "extracting_audio",
    "uploading",
    "transcribing",
    "analyzing",
    "exporting",
}


def utc_timestamp() -> float:
    return datetime.now(timezone.utc).timestamp()


def normalize_anchor(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())


class RecordingRelay:
    """Watch completed Quick Recorder files and hand them to the breakdown Agent."""

    def __init__(self, settings: Settings, database: Database):
        self.settings = settings
        self.database = database
        self.config_path = settings.relay_dir / "config.json"
        self.log_dir = settings.relay_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._config_lock = threading.RLock()
        self._scan_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._observations: dict[str, dict[str, float]] = {}
        self._last_scan = ""
        self._last_scan_result: dict[str, Any] = {}
        self._last_error = ""
        self._active_job_id: int | None = None
        self._ensure_config()

    def _default_config(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "recording_dir": str(self.settings.recording_dir),
            "stable_minutes": 15,
            "minimum_duration_minutes": 30,
            "poll_seconds": 60,
            # Files from before the bridge was installed are intentionally ignored.
            "ignore_before": utc_timestamp(),
        }

    def _ensure_config(self) -> None:
        if self.config_path.exists():
            return
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_config(self._default_config())

    def _read_config(self) -> dict[str, Any]:
        with self._config_lock:
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = self._default_config()
                self._write_config(data)
            defaults = self._default_config()
            defaults.update(data)
            return defaults

    def _write_config(self, data: dict[str, Any]) -> None:
        with self._config_lock:
            temporary = self.config_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.config_path)

    def update_config(self, changes: dict[str, Any]) -> dict[str, Any]:
        current = self._read_config()
        was_enabled = bool(current.get("enabled"))
        if "enabled" in changes:
            current["enabled"] = bool(changes["enabled"])
        if "recording_dir" in changes:
            path = Path(str(changes["recording_dir"] or "")).expanduser()
            if not path.is_absolute():
                raise ValueError("录屏目录必须是完整路径")
            current["recording_dir"] = str(path)
        if "stable_minutes" in changes:
            current["stable_minutes"] = max(1, min(120, int(changes["stable_minutes"])))
        if "minimum_duration_minutes" in changes:
            current["minimum_duration_minutes"] = max(
                0, min(600, int(changes["minimum_duration_minutes"]))
            )
        if "poll_seconds" in changes:
            current["poll_seconds"] = max(15, min(600, int(changes["poll_seconds"])))
        if not was_enabled and current["enabled"]:
            current["ignore_before"] = utc_timestamp()
            self._observations.clear()
        self._write_config(current)
        self._wake_event.set()
        return current

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        requeued = self.database.requeue_interrupted_integration_jobs(JOB_KIND)
        if requeued:
            self._wake_event.set()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="recording-relay",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            config = self._read_config()
            try:
                if config["enabled"]:
                    self.scan_once()
                    self._run_next_job()
                self._last_error = ""
            except Exception as exc:
                self._last_error = str(exc)
            wait_seconds = int(config.get("poll_seconds") or 60)
            self._wake_event.wait(wait_seconds)
            self._wake_event.clear()

    @staticmethod
    def _empty_scan_result() -> dict[str, Any]:
        return {
            "detected": 0,
            "matched": 0,
            "queued": 0,
            "skipped": 0,
            "waiting_stable": 0,
            "already_processed": 0,
            "unmatched": 0,
            "unmatched_files": [],
        }

    def scan_once(self, now: float | None = None) -> dict[str, Any]:
        if not self._scan_lock.acquire(blocking=False):
            result = self._empty_scan_result()
            result["busy"] = True
            return result
        try:
            config = self._read_config()
            if not config["enabled"]:
                return self._empty_scan_result()
            recording_dir = Path(config["recording_dir"])
            if not recording_dir.exists():
                raise FileNotFoundError(f"没有找到快抖录屏目录：{recording_dir}")
            current_time = now if now is not None else time.time()
            ignore_before = float(config.get("ignore_before") or 0)
            stable_seconds = int(config["stable_minutes"]) * 60
            minimum_duration = int(config["minimum_duration_minutes"]) * 60
            candidates = self.database.list_auto_breakdown_candidates()
            result = self._empty_scan_result()
            for path in recording_dir.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if stat.st_mtime < ignore_before:
                    continue
                result["detected"] += 1
                candidate = self._match_candidate(path, candidates)
                if not candidate:
                    result["unmatched"] += 1
                    if len(result["unmatched_files"]) < 3:
                        result["unmatched_files"].append(path.name)
                    continue
                result["matched"] += 1
                source_path = str(path.resolve())
                if self.database.find_integration_job(JOB_KIND, source_path):
                    result["already_processed"] += 1
                    continue
                if path.suffix.lower() == ".ts" and path.with_suffix(".mp4").exists():
                    result["already_processed"] += 1
                    continue
                observation = self._observations.get(source_path)
                if (
                    observation is None
                    or observation["size"] != float(stat.st_size)
                    or observation["mtime"] != float(stat.st_mtime)
                ):
                    self._observations[source_path] = {
                        "size": float(stat.st_size),
                        "mtime": float(stat.st_mtime),
                        "unchanged_since": current_time,
                    }
                    result["waiting_stable"] += 1
                    continue
                if current_time - observation["unchanged_since"] < stable_seconds:
                    result["waiting_stable"] += 1
                    continue
                duration = self._probe_duration(path)
                payload = {
                    "source_path": source_path,
                    "file_name": path.name,
                    "size_bytes": stat.st_size,
                    "duration_seconds": duration,
                    "output_path": "",
                }
                if duration < minimum_duration:
                    self.database.create_integration_job(
                        int(candidate["id"]),
                        JOB_KIND,
                        "skipped_short",
                        payload,
                        f"时长{duration / 60:.1f}分钟，低于自动拆解门槛",
                    )
                    result["skipped"] += 1
                else:
                    self.database.create_integration_job(
                        int(candidate["id"]),
                        JOB_KIND,
                        "queued",
                        payload,
                        "录像已完成，等待拆解",
                    )
                    self.database.update_candidate_status(
                        [int(candidate["id"])],
                        "recorded",
                    )
                    result["queued"] += 1
                self._observations.pop(source_path, None)
            self._last_scan = datetime.now().astimezone().isoformat(timespec="seconds")
            self._last_scan_result = result
            if result["queued"]:
                self._wake_event.set()
            # Keep the old field for callers written before detailed diagnostics.
            result["scanned"] = result["matched"]
            return result
        finally:
            self._scan_lock.release()

    @staticmethod
    def _match_candidate(
        path: Path,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        haystack = normalize_anchor(f"{path.parent.name}{path.stem}")
        matches = [
            candidate
            for candidate in candidates
            if normalize_anchor(str(candidate.get("anchor_name") or ""))
            and normalize_anchor(str(candidate.get("anchor_name") or "")) in haystack
        ]
        return max(
            matches,
            key=lambda item: len(normalize_anchor(str(item.get("anchor_name") or ""))),
            default=None,
        )

    def _find_ffprobe(self) -> Path | None:
        override = os.getenv("FFPROBE_PATH", "")
        if override and Path(override).exists():
            return Path(override)
        found = shutil.which("ffprobe")
        if found:
            return Path(found)
        bundled = (
            self.settings.project_dir.parent
            / "tools"
            / "ffmpeg"
            / "bits_unz"
            / "ffmpeg-master-latest-win64-gpl"
            / "bin"
            / "ffprobe.exe"
        )
        return bundled if bundled.exists() else None

    def _probe_duration(self, path: Path) -> float:
        ffprobe = self._find_ffprobe()
        if not ffprobe:
            raise RuntimeError("没有找到 ffprobe，无法确认录像是否完整")
        completed = subprocess.run(
            [
                str(ffprobe),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        try:
            duration = float(completed.stdout.strip())
        except ValueError as exc:
            raise RuntimeError(f"无法读取录像时长：{path.name}") from exc
        if duration <= 0:
            raise RuntimeError(f"录像时长无效：{path.name}")
        return duration

    def _run_next_job(self) -> None:
        if self._active_job_id is not None:
            return
        jobs = self.database.list_integration_jobs(JOB_KIND, limit=200)
        job = next((item for item in reversed(jobs) if item["status"] == "queued"), None)
        if not job:
            return
        self._run_job(job)

    def _run_job(self, job: dict[str, Any]) -> None:
        job_id = int(job["id"])
        candidate_id = int(job["candidate_id"]) if job.get("candidate_id") else None
        source_path = Path(str((job.get("payload") or {}).get("source_path") or ""))
        run_script = self.settings.breakdown_project_dir / "run.ps1"
        if not source_path.exists():
            self.database.update_integration_job(job_id, "failed", "录像文件已不存在")
            return
        if not run_script.exists():
            self.database.update_integration_job(job_id, "failed", "没有找到直播拆解 Agent")
            return
        self._active_job_id = job_id
        log_path = self.log_dir / f"job-{job_id}.log"
        self.database.update_integration_job(
            job_id,
            "starting",
            "正在启动直播拆解 Agent",
            {"log_path": str(log_path)},
        )
        command = [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(run_script),
            "run",
            str(source_path),
        ]
        try:
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            with log_path.open("a", encoding="utf-8") as log:
                process = subprocess.Popen(
                    command,
                    cwd=str(self.settings.breakdown_project_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creation_flags,
                )
                output_path = ""
                assert process.stdout is not None
                for raw_line in process.stdout:
                    line = raw_line.rstrip()
                    log.write(line + "\n")
                    log.flush()
                    status = self._status_from_progress(line)
                    if status:
                        self.database.update_integration_job(job_id, status, line)
                    if "8/8 完成：" in line:
                        output_path = line.split("8/8 完成：", 1)[1].strip()
                return_code = process.wait()
            if return_code != 0:
                self.database.update_integration_job(
                    job_id,
                    "failed",
                    f"拆解 Agent 运行失败，错误代码 {return_code}",
                )
                return
            if not output_path:
                expected = (
                    self.settings.breakdown_project_dir
                    / "workspace"
                    / "output"
                    / f"{source_path.stem}_拆解.xlsx"
                )
                output_path = str(expected) if expected.exists() else ""
            self.database.update_integration_job(
                job_id,
                "completed",
                "转写与分析完成",
                {"output_path": output_path},
            )
            if candidate_id:
                self.database.update_candidate_status([candidate_id], "analyzed")
        except Exception as exc:
            self.database.update_integration_job(job_id, "failed", str(exc))
        finally:
            self._active_job_id = None

    @staticmethod
    def _status_from_progress(line: str) -> str:
        mapping = [
            ("1/8", "checking"),
            ("2/8", "extracting_audio"),
            ("3/8", "uploading"),
            ("4/8", "transcribing"),
            ("5/8", "analyzing"),
            ("6/8", "analyzing"),
            ("7/8", "exporting"),
            ("8/8", "completed"),
        ]
        return next((status for marker, status in mapping if marker in line), "")

    def retry(self, job_id: int) -> dict[str, Any]:
        jobs = self.database.list_integration_jobs(JOB_KIND, limit=500)
        job = next((item for item in jobs if int(item["id"]) == job_id), None)
        if not job:
            raise ValueError("接力任务不存在")
        if job["status"] not in {"failed", "skipped_short"}:
            raise ValueError("只有失败或被时长门槛跳过的任务可以重试")
        self.database.update_integration_job(job_id, "queued", "已手动重新排队")
        self._wake_event.set()
        return {"queued": True, "job_id": job_id}

    def status(self) -> dict[str, Any]:
        config = self._read_config()
        jobs = self.database.list_integration_jobs(JOB_KIND, limit=50)
        enabled_candidates = self.database.list_auto_breakdown_candidates()
        return {
            "config": config,
            "recording_dir_exists": Path(config["recording_dir"]).exists(),
            "enabled_candidates": len(enabled_candidates),
            "enabled_candidate_details": [
                {
                    "id": candidate.get("id"),
                    "anchor_name": candidate.get("anchor_name", ""),
                    "douyin_id": candidate.get("douyin_id", ""),
                    "profile_url": candidate.get("profile_url", ""),
                    "theme_name": candidate.get("theme_name", ""),
                    "status": candidate.get("status", ""),
                }
                for candidate in enabled_candidates
            ],
            "active_job_id": self._active_job_id,
            "last_scan": self._last_scan,
            "last_scan_result": self._last_scan_result,
            "last_error": self._last_error,
            "jobs": jobs,
            "counts": {
                "active": sum(job["status"] in ACTIVE_STATUSES for job in jobs),
                "completed": sum(job["status"] == "completed" for job in jobs),
                "failed": sum(job["status"] == "failed" for job in jobs),
                "skipped": sum(job["status"] == "skipped_short" for job in jobs),
            },
        }
