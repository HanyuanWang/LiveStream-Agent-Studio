from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _find_tool(name: str, override: str, candidates: list[Path]) -> Path | None:
    if override:
        path = Path(override).expanduser().resolve()
        return path if path.exists() else None
    found = shutil.which(name)
    if found:
        return Path(found)
    return next((path for path in candidates if path.exists()), None)


@dataclass(frozen=True)
class Settings:
    project_dir: Path
    workspace_dir: Path
    dashscope_api_key: str
    dashscope_base_url: str
    asr_model: str
    text_model: str
    ffmpeg_path: Path | None
    ffprobe_path: Path | None
    oss_access_key_id: str
    oss_access_key_secret: str
    oss_security_token: str
    oss_endpoint: str
    oss_bucket: str

    @classmethod
    def load(cls, project_dir: Path | None = None) -> "Settings":
        root = (project_dir or PROJECT_DIR).resolve()
        load_dotenv(root / ".env")
        bundled_ffmpeg = root.parent / "tools" / "ffmpeg" / "bits_unz" / "ffmpeg-master-latest-win64-gpl" / "bin"
        ffmpeg = _find_tool("ffmpeg", os.getenv("FFMPEG_PATH", ""), [bundled_ffmpeg / "ffmpeg.exe"])
        ffprobe = _find_tool("ffprobe", os.getenv("FFPROBE_PATH", ""), [bundled_ffmpeg / "ffprobe.exe"])
        return cls(
            project_dir=root,
            workspace_dir=root / "workspace",
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            dashscope_base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com").rstrip("/"),
            asr_model=os.getenv("ASR_MODEL", "qwen3-asr-flash-filetrans"),
            text_model=os.getenv("TEXT_MODEL", "qwen-plus"),
            ffmpeg_path=ffmpeg,
            ffprobe_path=ffprobe,
            oss_access_key_id=os.getenv("ALIYUN_ACCESS_KEY_ID", ""),
            oss_access_key_secret=os.getenv("ALIYUN_ACCESS_KEY_SECRET", ""),
            oss_security_token=os.getenv("ALIYUN_SECURITY_TOKEN", ""),
            oss_endpoint=os.getenv("ALIYUN_OSS_ENDPOINT", ""),
            oss_bucket=os.getenv("ALIYUN_OSS_BUCKET", ""),
        )
