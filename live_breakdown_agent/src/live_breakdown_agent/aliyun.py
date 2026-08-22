from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from .http import request_json
from .models import TranscriptSegment, validate_transcript


class OssUploader:
    def __init__(self, endpoint: str, bucket: str, access_key_id: str, access_key_secret: str, security_token: str = ""):
        self.endpoint = endpoint
        self.bucket_name = bucket
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.security_token = security_token

    def upload_and_sign(self, local_path: Path, object_key: str, expires_seconds: int = 86400) -> str:
        try:
            import oss2  # type: ignore
        except ImportError as exc:
            raise RuntimeError("OSS 上传需要安装可选依赖：pip install -e .[aliyun-oss]") from exc
        if self.security_token:
            auth = oss2.StsAuth(self.access_key_id, self.access_key_secret, self.security_token)
        else:
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)
        if local_path.stat().st_size >= 32 * 1024 * 1024:
            checkpoint_dir = local_path.parent / ".oss_checkpoints"
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            last_bucket = -1

            def progress(consumed: int, total: int) -> None:
                nonlocal last_bucket
                percent = int(consumed * 100 / total) if total else 0
                bucket_number = percent // 10
                if bucket_number > last_bucket:
                    last_bucket = bucket_number
                    print(f"[直播拆解] OSS 上传 {min(percent, 100)}%", flush=True)

            oss2.resumable_upload(
                bucket,
                object_key,
                str(local_path),
                store=oss2.ResumableStore(root=str(checkpoint_dir)),
                multipart_threshold=32 * 1024 * 1024,
                part_size=8 * 1024 * 1024,
                progress_callback=progress,
                num_threads=3,
            )
        else:
            bucket.put_object_from_file(object_key, str(local_path))
        return bucket.sign_url("GET", object_key, expires_seconds, slash_safe=True)

    def delete(self, object_key: str) -> None:
        try:
            import oss2  # type: ignore
        except ImportError as exc:
            raise RuntimeError("OSS 清理需要安装可选依赖：pip install -e .[aliyun-oss]") from exc
        if self.security_token:
            auth = oss2.StsAuth(self.access_key_id, self.access_key_secret, self.security_token)
        else:
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)
        bucket.delete_object(object_key)


class DashScopeAsrClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "X-DashScope-Async": "enable"}

    def submit(self, audio_url: str) -> str:
        data = request_json(
            "POST",
            f"{self.base_url}/api/v1/services/audio/asr/transcription",
            self.headers,
            {
                "model": self.model,
                "input": {"file_url": audio_url},
                "parameters": {"channel_id": [0], "enable_itn": False, "enable_words": True},
            },
        )
        task_id = data.get("output", {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"转写任务提交失败: {data}")
        return str(task_id)

    def poll(self, task_id: str, interval_seconds: int = 10, timeout_seconds: int = 6 * 3600) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            data = request_json("GET", f"{self.base_url}/api/v1/tasks/{task_id}", self.headers)
            status = data.get("output", {}).get("task_status", "")
            if status == "SUCCEEDED":
                return data
            if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                raise RuntimeError(f"转写任务失败，状态={status}: {data}")
            time.sleep(interval_seconds)
        raise TimeoutError(f"等待转写超时: {task_id}")

    def download_result(self, task_result: dict[str, Any]) -> dict[str, Any]:
        output = task_result.get("output", {})
        url = output.get("result", {}).get("transcription_url")
        if not url:
            results = output.get("results", [])
            url = next((item.get("transcription_url") for item in results if item.get("transcription_url")), None)
        if not url:
            raise RuntimeError(f"任务完成但没有 transcription_url: {task_result}")
        with urllib.request.urlopen(url, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))


def parse_asr_result(data: dict[str, Any]) -> list[TranscriptSegment]:
    sentences: list[dict[str, Any]] = []
    for transcript in data.get("transcripts", []):
        sentences.extend(transcript.get("sentences", []))
    if not sentences:
        sentences = data.get("sentences", [])
    segments: list[TranscriptSegment] = []
    for item in sentences:
        uses_milliseconds = "begin_time" in item or "start_time" in item or "end_time" in item
        start_raw = item.get("begin_time", item.get("start_time", item.get("start", 0)))
        end_raw = item.get("end_time", item.get("end", 0))
        scale = 1000.0 if uses_milliseconds else 1.0
        text = str(item.get("text", "")).strip()
        if text:
            start = float(start_raw) / scale
            end = float(end_raw) / scale
            # 长音频偶尔返回带文本的零时长句；保留原文并赋予最小正时长。
            if end <= start:
                end = start + 0.01
            segments.append(TranscriptSegment(start, end, text))
    validate_transcript(segments)
    return segments
