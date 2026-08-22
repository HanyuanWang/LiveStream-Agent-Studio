from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, text=True, capture_output=True, encoding="utf-8", errors="replace")


def inspect_media(video_path: Path, ffprobe_path: Path) -> dict[str, Any]:
    result = _run([
        str(ffprobe_path), "-v", "error", "-show_entries",
        "format=duration,size,format_name:stream=index,codec_type,codec_name,sample_rate,channels,width,height",
        "-of", "json", str(video_path),
    ])
    data = json.loads(result.stdout)
    data["source"] = str(video_path.resolve())
    return data


def extract_audio(video_path: Path, audio_path: Path, ffmpeg_path: Path) -> Path:
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    _run([
        str(ffmpeg_path), "-y", "-i", str(video_path), "-map", "0:a:0",
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "flac", str(audio_path),
    ])
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        raise RuntimeError("音频提取失败：未生成有效文件")
    return audio_path

