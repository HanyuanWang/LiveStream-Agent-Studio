from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> None:
    """只将缺失变量载入进程环境；绝不打印配置值。"""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def dotenv_value(path: Path, wanted_key: str) -> str:
    """Read one current value without caching it in the process environment."""
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == wanted_key:
            return value.strip().strip('"').strip("'")
    return ""


@dataclass(frozen=True)
class Settings:
    project_dir: Path
    workspace_dir: Path
    database_path: Path
    web_dir: Path
    host: str
    port: int
    dashscope_api_key: str
    dashscope_base_url: str
    text_model: str
    breakdown_project_dir: Path
    quick_recorder_exe: Path
    chanmama_profile_dir: Path
    chanmama_download_dir: Path
    chanmama_state_path: Path
    chanmama_start_url: str
    report_dir: Path
    recording_dir: Path
    relay_dir: Path

    def current_quick_recorder_exe(self) -> Path | None:
        """Return the path most recently saved by the user in Studio settings."""
        value = dotenv_value(self.project_dir / ".env", "QUICK_RECORDER_EXE")
        if not value:
            value = dotenv_value(self.breakdown_project_dir / ".env", "QUICK_RECORDER_EXE")
        return Path(value).expanduser() if value else None

    @classmethod
    def load(cls, project_dir: Path | None = None) -> "Settings":
        root = (project_dir or PROJECT_DIR).resolve()
        breakdown = root.parent / "live_breakdown_agent"
        load_dotenv(root / ".env")
        load_dotenv(breakdown / ".env")
        workspace = root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "uploads").mkdir(exist_ok=True)
        (workspace / "exports").mkdir(exist_ok=True)
        (workspace / "reports").mkdir(exist_ok=True)
        (workspace / "relay").mkdir(exist_ok=True)
        chanmama_dir = workspace / "chanmama"
        chanmama_dir.mkdir(exist_ok=True)
        (chanmama_dir / "profile").mkdir(exist_ok=True)
        (chanmama_dir / "downloads").mkdir(exist_ok=True)
        return cls(
            project_dir=root,
            workspace_dir=workspace,
            database_path=workspace / "live_scout.db",
            web_dir=root / "web",
            host=os.getenv("LIVE_SCOUT_HOST", "127.0.0.1"),
            port=int(os.getenv("LIVE_SCOUT_PORT", "8765")),
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            dashscope_base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com").rstrip("/"),
            text_model=os.getenv("TEXT_MODEL", "qwen-plus"),
            breakdown_project_dir=breakdown,
            quick_recorder_exe=Path(os.getenv("QUICK_RECORDER_EXE", "").strip() or (workspace / ".quick-recorder-not-configured.exe")),
            # ``profile`` was created by an older Chrome/Playwright flow and
            # can become permanently crash-looped after an interrupted run.
            # Keep it intact for recovery, but use a fresh, versioned profile
            # for the current foreground/CDP browser workflow.
            chanmama_profile_dir=chanmama_dir / "profile_v2",
            chanmama_download_dir=chanmama_dir / "downloads",
            chanmama_state_path=chanmama_dir / "state.json",
            chanmama_start_url=os.getenv("CHANMAMA_START_URL", "https://www.chanmama.com/"),
            report_dir=workspace / "reports",
            recording_dir=Path(
                os.getenv(
                    "QUICK_RECORDING_DIR",
                    str(Path.home() / "Desktop" / "录屏"),
                )
            ),
            relay_dir=workspace / "relay",
        )
