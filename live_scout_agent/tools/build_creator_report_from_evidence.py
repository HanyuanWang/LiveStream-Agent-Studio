from __future__ import annotations

import argparse
import json
from pathlib import Path

from live_scout_agent.config import Settings
from live_scout_agent.creator_reports import (
    analyze_creator,
    build_report_docx,
    safe_name,
    validate_detail_evidence,
)
from live_scout_agent.database import Database


def main() -> None:
    parser = argparse.ArgumentParser(description="用已采集的完整网页证据生成达人拆解报告")
    parser.add_argument("query", help="达人名称关键词或候选ID")
    parser.add_argument("evidence", type=Path, help="完整网页证据JSON")
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

    evidence = validate_detail_evidence(
        json.loads(args.evidence.read_text(encoding="utf-8"))
    )
    name = str(selected.get("anchor_name") or f"达人{selected['id']}")
    safe = safe_name(name)
    evidence_path = settings.report_dir / f"{safe}_蝉妈妈网页完整数据.json"
    evidence_temp = settings.report_dir / f".{safe}_蝉妈妈网页完整数据.tmp.json"
    evidence_temp.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    evidence_temp.replace(evidence_path)

    analysis = analyze_creator(selected, evidence, settings)
    report_path = settings.report_dir / f"{safe}_达人拆解报告.docx"
    report_temp = settings.report_dir / f".{safe}_达人拆解报告.tmp.docx"
    build_report_docx(selected, analysis, report_temp)
    report_temp.replace(report_path)
    database.update_candidate_status([int(selected["id"])], "analyzed")
    print(
        json.dumps(
            {
                "anchor_name": name,
                "report": str(report_path),
                "evidence": str(evidence_path),
                "pages": len(evidence.get("pages") or []),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
