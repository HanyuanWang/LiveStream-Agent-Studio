from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Settings
from .pipeline import LiveBreakdownAgent


def doctor(settings: Settings) -> int:
    checks = {
        "ffmpeg": str(settings.ffmpeg_path) if settings.ffmpeg_path else "MISSING",
        "ffprobe": str(settings.ffprobe_path) if settings.ffprobe_path else "MISSING",
        "excel": "openpyxl",
        "dashscope_api_key": "SET" if settings.dashscope_api_key else "MISSING",
        "oss": "SET" if all([settings.oss_endpoint, settings.oss_bucket, settings.oss_access_key_id, settings.oss_access_key_secret]) else "MISSING",
        "oss_endpoint": settings.oss_endpoint or "MISSING",
        "oss_bucket": settings.oss_bucket or "MISSING",
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(checks[key] != "MISSING" for key in ["ffmpeg", "ffprobe"]) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="直播拆解 Agent：完整转写后，再做事件分析，最终只交付一个 Excel。")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="检查本地工具和云端配置")
    run = sub.add_parser("run", help="处理一个直播录屏")
    run.add_argument("video", type=Path)
    run.add_argument("--audio-url", default="", help="已有可下载音频 URL 时可跳过 OSS 上传")
    resume = sub.add_parser("resume-job", help="从已有任务的 audio.flac 断点续跑")
    resume.add_argument("job_dir", type=Path)
    analyze = sub.add_parser("analyze-transcript", help="从已完成的 transcript.json 开始分析")
    analyze.add_argument("transcript", type=Path)
    analyze.add_argument("output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.load()
    try:
        if args.command == "doctor":
            return doctor(settings)
        agent = LiveBreakdownAgent(settings)
        if args.command == "run":
            output = agent.run(args.video, args.audio_url)
        elif args.command == "resume-job":
            output = agent.resume_job(args.job_dir)
        else:
            output = agent.analyze_transcript_file(args.transcript, args.output)
        print(output)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
