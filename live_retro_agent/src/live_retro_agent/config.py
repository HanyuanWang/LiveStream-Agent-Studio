from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
WORKSPACE = PROJECT_DIR / "workspace"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    project_dir: Path
    workspace: Path
    python: str
    port: int
    dashscope_key: str
    dashscope_url: str
    text_model: str

    @classmethod
    def load(cls) -> "Settings":
        load_env(PROJECT_DIR / ".env")
        load_env(PROJECT_DIR.parent / "live_breakdown_agent" / ".env")
        return cls(
            project_dir=PROJECT_DIR,
            workspace=WORKSPACE,
            python=os.sys.executable,
            port=int(os.getenv("LIVE_RETRO_PORT", "8775")),
            dashscope_key=os.getenv("DASHSCOPE_API_KEY", ""),
            dashscope_url=os.getenv(
                "DASHSCOPE_CHAT_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            ),
            text_model=os.getenv("TEXT_MODEL", "qwen-plus"),
        )
