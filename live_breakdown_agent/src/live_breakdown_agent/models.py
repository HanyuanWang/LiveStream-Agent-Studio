from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any


def format_hms(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str

    def validate(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"非法时间段: {self.start}-{self.end}")
        if not self.text.strip():
            raise ValueError("逐字稿文本不能为空")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventRow:
    start: float
    end: float
    event: str
    transcript: str
    is_key_event: bool = False

    @property
    def timestamp(self) -> str:
        start_second = max(0, math.floor(self.start))
        end_second = max(start_second + 1, math.ceil(self.end))
        return f"{format_hms(start_second)}-{format_hms(end_second)}"

    def validate(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"非法事件时间段: {self.start}-{self.end}")
        if not self.event.strip() or not self.transcript.strip():
            raise ValueError("事件和逐字稿不能为空")

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "start": self.start,
            "end": self.end,
            "event": self.event,
            "transcript": self.transcript,
            "is_key_event": self.is_key_event,
        }


def validate_transcript(segments: list[TranscriptSegment], max_backtrack_seconds: float = 0.5) -> None:
    if not segments:
        raise ValueError("转写结果为空")
    previous_start = -1.0
    for segment in segments:
        segment.validate()
        if segment.start + max_backtrack_seconds < previous_start:
            raise ValueError("转写时间戳乱序")
        previous_start = segment.start


def validate_event_rows(rows: list[EventRow]) -> None:
    if not rows:
        raise ValueError("事件分析结果为空")
    previous_start = -1.0
    for row in rows:
        row.validate()
        if row.start < previous_start:
            raise ValueError("事件行时间戳乱序")
        previous_start = row.start
