from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .analysis import attach_timeline, build_review, infer_live_start, parse_breakdown, parse_minute, parse_orders
from .config import Settings
from .traffic_outputs import generate_outputs
from .workbooks import extract_xlsx, iter_sheets, read_csv

Progress = Callable[[int, str], None]


def process_job(job_dir: Path, inputs: dict[str, Path], options: dict[str, Any], settings: Settings, progress: Progress) -> dict[str, Any]:
    warnings: list[str] = []
    inventory: list[dict[str, Any]] = []
    progress(8, "检查逐字稿拆解 Excel")
    breakdown_data = extract_xlsx(inputs["breakdown"], job_dir / "breakdown.json", settings)
    sentences, transcript_warnings = parse_breakdown(breakdown_data)
    warnings.extend(transcript_warnings)
    inventory.append({"role": "逐字稿拆解", "file": inputs["breakdown"].name, "detail": f"识别 {len(sentences)} 句"})

    extracted: dict[str, dict[str, Any]] = {}
    for role in ("orders", "minute", "session"):
        path = inputs.get(role)
        if not path:
            continue
        progress(15 + len(extracted) * 8, f"读取{ {'orders':'订单明细','minute':'分钟趋势','session':'整场数据'}[role] }")
        if path.suffix.lower() == ".csv":
            extracted[role] = {"source": str(path), "sheets": [{"name": "CSV", "rows": read_csv(path)}]}
        else:
            extracted[role] = extract_xlsx(path, job_dir / f"{role}.json", settings)

    progress(38, "识别流量与直播时间口径")
    # This Agent deliberately ignores transaction files. Its only analytical
    # scope is the relationship between speech and livestream traffic.
    orders: list[dict[str, Any]] = []
    minute_data = extracted.get("minute", {"sheets": []})
    minutes = parse_minute(list(iter_sheets(minute_data)))
    if inputs.get("minute"):
        inventory.append({"role": "分钟趋势", "file": inputs["minute"].name, "detail": f"识别 {len(minutes)} 条时间记录"})
    else:
        warnings.append("未上传分钟趋势：无法分析话术与流量变化。")
    if inputs.get("session"):
        sheets = extracted.get("session", {}).get("sheets", [])
        inventory.append({"role": "整场数据", "file": inputs["session"].name, "detail": f"读取 {len(sheets)} 个工作表，作为整场口径参考"})
    else:
        pass

    duration = max(s["end_seconds"] for s in sentences)
    live_start, start_source = infer_live_start(options.get("live_start", ""), minutes, list(inputs.values()), duration)
    if not live_start:
        warnings.append("未识别直播开始时间：流量分钟数据不能准确映射到视频话术时间轴。")
    inventory.append({"role": "直播开始时间", "file": start_source, "detail": live_start.strftime("%Y-%m-%d %H:%M:%S") if live_start else "缺失"})
    official_gmv = None

    progress(50, "建立逐句话术与分钟流量的统一时间线")
    timeline = attach_timeline(sentences, orders, minutes, live_start, official_gmv)
    progress(62, "识别强弱流量时段与话术循环")
    review = build_review(sentences, timeline, warnings, settings)

    progress(82, "生成流量与话术分析 Excel 和 Word")
    session_name = options.get("session_name") or inputs["breakdown"].stem.replace("_拆解", "")
    outputs = generate_outputs(job_dir, session_name, sentences, timeline, review, inventory, settings)
    analysis_path = job_dir / "analysis.json"
    analysis_path.write_text(json.dumps({"session_name": session_name, "inventory": inventory, "sentences": sentences, "timeline": timeline, "review": review}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    progress(91, "执行输出文件完整性检查")
    for output in outputs:
        path = Path(output["path"])
        if not path.exists() or path.stat().st_size < 100:
            raise RuntimeError(f"输出文件为空或未生成：{path.name}")

    shared_dir = settings.workspace / "output" / job_dir.name
    if shared_dir.exists():
        shutil.rmtree(shared_dir)
    shutil.copytree(job_dir / "output", shared_dir)
    for item in outputs:
        item["shared_path"] = str(shared_dir / Path(item["path"]).name)
    progress(100, "复盘完成")
    headline = str(review["conclusions"].get("headline", "流量与话术分析完成"))
    return {"session_name": session_name, "summary": headline, "outputs": outputs, "inventory": inventory, "warnings": review["warnings"]}
