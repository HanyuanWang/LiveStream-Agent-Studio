from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


STAGES = [
    "created",
    "media_inspected",
    "audio_extracted",
    "audio_uploaded",
    "transcription_submitted",
    "transcription_complete",
    "transcription_validated",
    "analysis_complete",
    "excel_exported",
]


@dataclass
class JobState:
    job_id: str
    source_video: str
    stage: str = "created"
    task_id: str = ""
    audio_url: str = ""
    error: str = ""
    updated_at: str = ""


class JobStore:
    def __init__(self, job_dir: Path):
        self.job_dir = job_dir
        self.path = job_dir / "state.json"
        job_dir.mkdir(parents=True, exist_ok=True)

    def save(self, state: JobState) -> None:
        state.updated_at = datetime.now().isoformat(timespec="seconds")
        self.path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> JobState:
        return JobState(**json.loads(self.path.read_text(encoding="utf-8")))

    def advance(self, state: JobState, stage: str, **updates: Any) -> None:
        if stage not in STAGES:
            raise ValueError(f"未知阶段: {stage}")
        if STAGES.index(stage) < STAGES.index(state.stage):
            raise ValueError(f"任务不能从 {state.stage} 回退到 {stage}")
        state.stage = stage
        for key, value in updates.items():
            setattr(state, key, value)
        self.save(state)

