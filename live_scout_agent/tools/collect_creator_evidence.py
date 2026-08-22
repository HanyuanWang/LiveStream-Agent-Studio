from __future__ import annotations

import argparse
import json
from pathlib import Path

from live_scout_agent.config import Settings
from live_scout_agent.creator_reports import collect_chanmama_evidence
from live_scout_agent.database import Database


def main() -> None:
    parser = argparse.ArgumentParser(description="采集指定达人的蝉妈妈网页完整数据")
    parser.add_argument("query", help="达人名称关键词或候选ID")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    settings = Settings.load()
    database = Database(settings.database_path)
    candidates = database.list_candidates(limit=5000)
    if args.query.isdigit():
        selected = next(
            (candidate for candidate in candidates if int(candidate["id"]) == int(args.query)),
            None,
        )
    else:
        selected = next(
            (
                candidate
                for candidate in candidates
                if args.query.lower() in str(candidate.get("anchor_name") or "").lower()
            ),
            None,
        )
    if selected is None:
        raise SystemExit(f"未找到达人：{args.query}")

    evidence = collect_chanmama_evidence(selected, settings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "anchor_name": selected.get("anchor_name"),
                "pages": len(evidence.get("pages") or []),
                "warnings": evidence.get("warnings") or [],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
