from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import Settings
from .workbooks import clean, find_header, hms, iter_sheets, normalize_label, parse_datetime, parse_hms, parse_number


PHASE_TERMS = {
    "痛点": ["睡不好", "睡不着", "起夜", "没精神", "疲惫", "乏力", "怕冷", "手脚冰凉", "脸色", "暗黄", "掉头发", "脱发", "皱纹", "衰老", "气血不足", "上火", "没效果"],
    "塑品": ["你看我", "我今年", "61岁", "六十一", "我的脸", "我的头发", "我的皮肤", "我的状态", "反馈", "复购", "好评", "案例", "专利", "成分", "含量", "小分子", "吸收", "不上火"],
    "活动机制": ["原价", "到手", "今天只要", "价格", "套餐", "一个月", "两个月", "三个月", "半年", "送", "加赠", "优惠", "链接"],
    "卡库存": ["库存", "断货", "没货", "卖光", "只剩", "补货", "上架", "下架", "加库存", "最后一轮", "占单", "释放"],
    "逼单": ["下播", "马上结束", "最后两分钟", "赶紧拍", "去拍", "快点拍", "付款", "不要等", "错过", "没有了", "不讲了"],
}
PHASE_ORDER = ["痛点", "塑品", "活动机制", "卡库存", "逼单"]


def parse_range(value: Any) -> tuple[float | None, float | None]:
    text = clean(value)
    tokens = re.findall(r"\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?", text)
    if not tokens:
        return None, None
    start = parse_hms(tokens[0])
    end = parse_hms(tokens[1]) if len(tokens) > 1 else None
    return start, end


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    pieces = [x.strip() for x in re.split(r"(?<=[。！？!?；;])|\n+", text) if x.strip()]
    result: list[str] = []
    for piece in pieces:
        if len(piece) <= 70:
            result.append(piece)
        else:
            chunks = [x.strip() for x in re.split(r"(?<=[，,])", piece) if x.strip()]
            buffer = ""
            for chunk in chunks:
                if buffer and len(buffer) + len(chunk) > 55:
                    result.append(buffer)
                    buffer = chunk
                else:
                    buffer += chunk
            if buffer:
                result.append(buffer)
    return result or [text]


def classify(text: str, event: str) -> tuple[str, str]:
    scores = {phase: sum(text.count(term) for term in terms) for phase, terms in PHASE_TERMS.items()}
    event_scores = {
        "痛点": ["痛点"], "塑品": ["卖点", "功效", "原理", "人设", "案例", "信任"],
        "活动机制": ["价格", "机制", "套餐", "赠品", "优惠"], "卡库存": ["库存", "上链接", "下架", "返场"],
        "逼单": ["催单", "下播", "倒计时", "付款"],
    }
    for phase, terms in event_scores.items():
        if any(t in event for t in terms):
            scores[phase] += 1
    precedence = ["逼单", "卡库存", "活动机制", "痛点", "塑品"]
    if not any(scores.values()):
        return "其他", "互动或过渡"
    phase = max(precedence, key=lambda p: (scores[p], -precedence.index(p)))
    if phase == "痛点":
        subtype = "具体身体/外貌问题" if any(x in text for x in ["睡", "头发", "脸", "暗黄", "累", "起夜"]) else "泛化问题"
    elif phase == "塑品":
        subtype = "主播本人状态自证" if any(x in text for x in ["你看我", "我今年", "61岁", "六十一", "我的脸", "我的头发"]) else "产品证据与价值"
    elif phase == "活动机制":
        subtype = "套餐价格与到手量" if any(x in text for x in ["原价", "到手", "套餐", "一个月", "半年"]) else "优惠机制"
    elif phase == "卡库存":
        subtype = "真实上下架/补货" if any(x in text for x in ["上架", "下架", "补货", "加库存"]) else "稀缺提示"
    else:
        subtype = "下播/截止逼单" if any(x in text for x in ["下播", "结束", "最后"]) else "行动指令"
    return phase, subtype


def parse_breakdown(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    source_rows: list[dict[str, Any]] = []
    for sheet_name, rows in iter_sheets(data):
        found = find_header(rows, [["时间戳", "时间"], ["事件"], ["逐字稿", "话术", "原文"]])
        if not found:
            continue
        header_idx, mapping = found
        for idx, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
            timestamp = row[mapping["时间戳"]] if mapping["时间戳"] < len(row) else ""
            event = clean(row[mapping["事件"]] if mapping["事件"] < len(row) else "")
            text = clean(row[mapping["逐字稿"]] if mapping["逐字稿"] < len(row) else "")
            start, end = parse_range(timestamp)
            if text and start is not None:
                source_rows.append({"sheet": sheet_name, "source_row": idx, "timestamp": clean(timestamp), "start": start, "end": end, "event": event or "未分类", "text": text})
    if not source_rows:
        raise RuntimeError("拆解 Excel 中没有找到“时间戳—事件—逐字稿”表头。")
    source_rows.sort(key=lambda x: x["start"])
    for idx, row in enumerate(source_rows):
        if row["end"] is None:
            row["end"] = source_rows[idx + 1]["start"] if idx + 1 < len(source_rows) else row["start"] + 60
        if row["end"] <= row["start"]:
            row["end"] = row["start"] + 3
    sentences: list[dict[str, Any]] = []
    sentence_id = 0
    for block in source_rows:
        parts = split_sentences(block["text"])
        weights = [max(2, len(re.sub(r"\W", "", part))) for part in parts]
        total = sum(weights) or len(parts)
        cursor = float(block["start"])
        duration = max(float(block["end"]) - float(block["start"]), len(parts) * 1.2)
        for index, (part, weight) in enumerate(zip(parts, weights)):
            sentence_id += 1
            end = float(block["end"]) if index == len(parts) - 1 else cursor + duration * weight / total
            phase, subtype = classify(part, block["event"])
            sentences.append({
                "sentence_id": sentence_id, "start_seconds": round(cursor, 2), "end_seconds": round(end, 2),
                "video_start": hms(cursor), "video_end": hms(end), "time_source": "estimated",
                "event": block["event"], "phase": phase, "subtype": subtype, "text": part,
                "source_sheet": block["sheet"], "source_row": block["source_row"], "source_timestamp": block["timestamp"],
            })
            cursor = end
    warnings.append("逐句话术时间由拆解区间按句长保守分配，标记为 estimated；不是原生逐词秒级时间。")
    return sentences, warnings


def optional_col(header: list[Any], aliases: list[str]) -> int | None:
    norms = [normalize_label(x) for x in header]
    candidates = [normalize_label(x) for x in aliases]
    return next((i for i, val in enumerate(norms) if val and any(c in val or val in c for c in candidates)), None)


def parse_orders(rows_by_sheet: list[tuple[str, list[list[Any]]]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for sheet_name, rows in rows_by_sheet:
        found = find_header(rows, [["支付完成时间", "支付时间", "成交时间"], ["订单应付金额", "实付金额", "成交金额", "订单金额"]])
        if not found:
            continue
        header_idx, mapping = found
        header = rows[header_idx]
        cols = {
            "pay_time": mapping["支付完成时间"], "paid_amount": mapping["订单应付金额"],
            "product": optional_col(header, ["选购商品", "商品名称", "商品"]),
            "quantity": optional_col(header, ["商品数量", "数量", "成交件数"]),
            "order_id": optional_col(header, ["主订单编号", "订单编号", "子订单编号"]),
            "order_status": optional_col(header, ["订单状态"]), "aftersale": optional_col(header, ["售后状态", "退款状态"]),
        }
        for source_row, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
            def value(name: str) -> Any:
                col = cols.get(name)
                return row[col] if col is not None and col < len(row) else ""
            pay_time = parse_datetime(value("pay_time"))
            amount = parse_number(value("paid_amount"))
            if not pay_time and amount == 0:
                continue
            status, aftersale = clean(value("order_status")), clean(value("aftersale"))
            refunded = "退款成功" in aftersale or ("关闭" in status and pay_time is not None)
            results.append({
                "source_sheet": sheet_name, "source_row": source_row, "pay_time": pay_time,
                "paid_amount": amount, "product": clean(value("product")) or "商品未标注",
                "quantity": int(parse_number(value("quantity")) or 0), "order_id": clean(value("order_id")),
                "order_status": status, "aftersale_status": aftersale, "is_refunded": refunded,
                "is_valid": bool(pay_time) and not refunded,
            })
    return results


def parse_minute(rows_by_sheet: list[tuple[str, list[list[Any]]]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    minute_sheets = [(name, rows) for name, rows in rows_by_sheet if "分钟" in normalize_label(name)]
    selected_sheets = minute_sheets or rows_by_sheet
    for sheet_name, rows in selected_sheets:
        found = find_header(rows, [["时间", "日期时间", "分钟"]])
        if not found:
            continue
        header_idx, mapping = found
        header = rows[header_idx]
        metric_aliases = {
            "viewers": ["进入直播间人数", "观看人数", "直播间观看人数"],
            "leavers": ["直播间离开人数", "离开直播间人数", "离开人数"],
            "online": ["实时在线人数", "在线人数", "平均在线人数"],
            "exposure": ["商品曝光人数", "曝光人数", "直播间曝光人数"],
            "interaction": ["评论次数", "互动人数", "内容互动人数"],
            "likes": ["点赞次数", "点赞人数"],
            "followers": ["新增粉丝数", "新增关注数", "关注人数"],
            "product_clicks": ["商品点击人数", "点击人数"],
            "watch_seconds": ["人均观看时长", "平均观看时长", "观看时长"],
        }
        cols = {name: optional_col(header, aliases) for name, aliases in metric_aliases.items()}
        if not any(col is not None for col in cols.values()):
            continue
        for source_row, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
            time_value = row[mapping["时间"]] if mapping["时间"] < len(row) else ""
            dt = parse_datetime(time_value)
            if not dt:
                continue
            record: dict[str, Any] = {"source_sheet": sheet_name, "source_row": source_row, "time": dt, "original_time": clean(time_value)}
            for name, col in cols.items():
                value = row[col] if col is not None and col < len(row) else 0
                if name == "watch_seconds":
                    text = clean(value)
                    hours = float(re.search(r"(\d+(?:\.\d+)?)\s*小时", text).group(1)) if re.search(r"(\d+(?:\.\d+)?)\s*小时", text) else 0
                    minutes_value = float(re.search(r"(\d+(?:\.\d+)?)\s*分钟", text).group(1)) if re.search(r"(\d+(?:\.\d+)?)\s*分钟", text) else 0
                    seconds_value = float(re.search(r"(\d+(?:\.\d+)?)\s*秒", text).group(1)) if re.search(r"(\d+(?:\.\d+)?)\s*秒", text) else 0
                    record[name] = hours * 3600 + minutes_value * 60 + seconds_value if text and any(x in text for x in ("小时", "分钟", "秒")) else parse_number(value)
                else:
                    record[name] = parse_number(value)
            results.append(record)
    return results


def infer_live_start(explicit: str, minute_rows: list[dict[str, Any]], paths: list[Path], duration: float) -> tuple[datetime | None, str]:
    if explicit:
        dt = parse_datetime(explicit)
        if not dt:
            raise RuntimeError("直播开始时间格式无法识别，请使用 2026-08-10 13:40:00。")
        return dt, "用户填写"
    full_minute = [r["time"] for r in minute_rows if r["time"].year >= 2000]
    if full_minute:
        return min(full_minute).replace(second=0, microsecond=0), "分钟数据最早时间"
    for path in paths:
        match = re.search(r"(20\d{2})[-_年](\d{2})[-_月](\d{2}).*?(\d{2})[-_:时](\d{2})[-_:分](\d{2})", path.name)
        if match:
            return datetime(*map(int, match.groups())), f"文件名推断：{path.name}"
    return None, "未识别"


def attach_timeline(sentences: list[dict[str, Any]], orders: list[dict[str, Any]], minutes: list[dict[str, Any]], live_start: datetime | None, official_gmv: float | None) -> dict[str, Any]:
    duration = max((s["end_seconds"] for s in sentences), default=0.0)
    live_end = live_start + timedelta(seconds=duration) if live_start else None
    live_orders: list[dict[str, Any]] = []
    for order in orders:
        offset = (order["pay_time"] - live_start).total_seconds() if live_start and order["pay_time"] else None
        order["pay_offset"] = offset
        order["video_time"] = hms(offset) if offset is not None else "缺失"
        order["in_live"] = offset is not None and -60 <= offset <= duration + 300
        if order["in_live"] and order["paid_amount"] > 0:
            live_orders.append(order)
    minute_rows: list[dict[str, Any]] = []
    for minute in minutes:
        dt = minute["time"]
        if live_start and dt.year == 1900:
            dt = datetime.combine(live_start.date(), dt.time())
        offset = (dt - live_start).total_seconds() if live_start else None
        minute["offset"] = offset
        minute["video_time"] = hms(offset) if offset is not None else minute["original_time"]
        if offset is None or -60 <= offset <= duration + 300:
            minute_rows.append(minute)
    raw_minute_gmv = sum(r.get("gmv", 0) for r in minute_rows)
    factor = official_gmv / raw_minute_gmv if official_gmv and raw_minute_gmv > 0 else 1.0
    for minute in minute_rows:
        minute["calibrated_gmv"] = minute.get("gmv", 0) * factor
    for sentence in sentences:
        start, end = sentence["start_seconds"], sentence["end_seconds"]
        if live_start:
            sentence["actual_start"] = (live_start + timedelta(seconds=start)).strftime("%Y-%m-%d %H:%M:%S")
            sentence["actual_end"] = (live_start + timedelta(seconds=end)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            sentence["actual_start"] = sentence["actual_end"] = "缺失"
        for minutes_after in (1, 3, 5):
            linked = [
                o for o in live_orders
                if o.get("is_valid") and end < o["pay_offset"] <= end + minutes_after * 60
            ]
            sentence[f"orders_{minutes_after}m"] = len(linked)
            sentence[f"gmv_{minutes_after}m"] = round(sum(o["paid_amount"] for o in linked), 2)
            sentence[f"units_{minutes_after}m"] = sum(o["quantity"] for o in linked)
        current = [m for m in minute_rows if m.get("offset") is not None and start - 60 < m["offset"] <= end + 60]
        sentence["traffic_viewers"] = round(sum(m.get("viewers", 0) for m in current), 2)
        sentence["traffic_online"] = round(max([m.get("online", 0) for m in current] or [0]), 2)
        sentence["traffic_clicks"] = round(sum(m.get("product_clicks", 0) for m in current), 2)
        sentence["traffic_leavers"] = round(sum(m.get("leavers", 0) for m in current), 2)
        sentence["traffic_interaction"] = round(sum(m.get("interaction", 0) for m in current), 2)
        sentence["traffic_likes"] = round(sum(m.get("likes", 0) for m in current), 2)
        sentence["traffic_followers"] = round(sum(m.get("followers", 0) for m in current), 2)
        sentence["traffic_exposure"] = round(sum(m.get("exposure", 0) for m in current), 2)
        sentence["traffic_watch_seconds"] = round(sum(m.get("watch_seconds", 0) for m in current) / max(len(current), 1), 2)
    return {
        "duration": duration, "live_start": live_start, "live_end": live_end, "orders": orders,
        "live_orders": live_orders, "minutes": minute_rows, "raw_minute_gmv": raw_minute_gmv,
        "calibration_factor": factor, "official_gmv": official_gmv,
    }


def summarize_interval(start: float, end: float, sentences: list[dict[str, Any]], timeline: dict[str, Any]) -> dict[str, Any]:
    orders = [o for o in timeline["live_orders"] if start <= o["pay_offset"] < end]
    valid = [o for o in orders if o["is_valid"]]
    ss = [s for s in sentences if s["end_seconds"] >= start and s["start_seconds"] < end]
    phase_seconds = defaultdict(float)
    for sentence in ss:
        overlap = max(0.0, min(end, sentence["end_seconds"]) - max(start, sentence["start_seconds"]))
        phase_seconds[sentence["phase"]] += overlap
    minutes = max((end - start) / 60, 0.01)
    excerpt = "".join(s["text"] for s in ss[:8])[:500]
    return {
        "start": start, "end": end, "video_time": f"{hms(start)}–{hms(end)}", "minutes": round(minutes, 2),
        "paid_orders": len(orders), "paid_gmv": round(sum(o["paid_amount"] for o in orders), 2),
        "valid_orders": len(valid), "valid_gmv": round(sum(o["paid_amount"] for o in valid), 2),
        "gmv_per_min": round(sum(o["paid_amount"] for o in valid) / minutes, 2),
        "phase_seconds": dict(phase_seconds), "phase_sequence": "→".join([p for p in PHASE_ORDER if phase_seconds.get(p)]),
        "excerpt": excerpt, "product": Counter(o["product"] for o in valid).most_common(1)[0][0] if valid else "无成交商品",
    }


def detect_blocks_and_waves(sentences: list[dict[str, Any]], timeline: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    duration = timeline["duration"]
    blocks = [summarize_interval(start, min(start + 600, duration), sentences, timeline) for start in range(0, max(1, math.ceil(duration / 600)) * 600, 600) if start < duration]
    anchors = [0.0]
    last = 0.0
    for sentence in sentences:
        marker = sentence["event"] + sentence["text"]
        if any(term in marker for term in ["上架", "下架", "加库存", "补货", "返场", "最后一轮", "重新上"]):
            if sentence["start_seconds"] - last >= 180:
                anchors.append(sentence["start_seconds"])
                last = sentence["start_seconds"]
    cursor = 0.0
    while cursor + 720 < duration:
        cursor += 720
        if all(abs(cursor - a) > 180 for a in anchors):
            anchors.append(cursor)
    anchors = sorted(set(round(x, 2) for x in anchors if x < duration))
    if not anchors or anchors[0] != 0:
        anchors.insert(0, 0.0)
    waves = []
    for idx, start in enumerate(anchors):
        end = anchors[idx + 1] if idx + 1 < len(anchors) else duration
        if end - start < 90 and waves:
            waves[-1] = summarize_interval(waves[-1]["start"], end, sentences, timeline) | {"wave": waves[-1]["wave"]}
            continue
        wave = summarize_interval(start, end, sentences, timeline)
        wave["wave"] = f"波次{len(waves)+1}"
        waves.append(wave)
    return blocks, waves


def candidate_passages(sentences: list[dict[str, Any]], timeline: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for i in range(0, len(sentences), 4):
        group = sentences[i : i + 8]
        if not group:
            continue
        start, end = group[0]["start_seconds"], group[-1]["end_seconds"]
        if end - start > 150:
            group = group[:4]
            end = group[-1]["end_seconds"]
        linked_1 = [o for o in timeline["live_orders"] if o.get("is_valid") and end < o["pay_offset"] <= end + 60]
        linked_3 = [o for o in timeline["live_orders"] if o.get("is_valid") and end < o["pay_offset"] <= end + 180]
        linked_5 = [o for o in timeline["live_orders"] if o.get("is_valid") and end < o["pay_offset"] <= end + 300]
        gmv3 = sum(o["paid_amount"] for o in linked_3)
        baseline = [o for o in timeline["live_orders"] if max(0, start - 180) <= o["pay_offset"] < start and o["is_valid"]]
        baseline_gmv = sum(o["paid_amount"] for o in baseline)
        phase_counts = Counter(s["phase"] for s in group)
        candidates.append({
            "start": start, "end": end, "video_time": f"{hms(start)}–{hms(end)}", "phase": phase_counts.most_common(1)[0][0],
            "phase_mix": "、".join(f"{k}{v}" for k, v in phase_counts.items()), "text": "".join(s["text"] for s in group),
            "orders_1m": len(linked_1), "gmv_1m": round(sum(o["paid_amount"] for o in linked_1), 2),
            "orders_3m": len(linked_3), "gmv_3m": round(gmv3, 2), "orders_5m": len(linked_5),
            "gmv_5m": round(sum(o["paid_amount"] for o in linked_5), 2),
            "baseline_3m_gmv": round(baseline_gmv, 2), "lift_vs_baseline": round(gmv3 - baseline_gmv, 2),
            "products": "、".join(x for x, _ in Counter(o["product"] for o in linked_3).most_common(3)) or "无",
        })
    deduped = []
    for item in sorted(candidates, key=lambda x: (x["gmv_3m"], x["orders_3m"], x["lift_vs_baseline"]), reverse=True):
        if item["orders_3m"] == 0:
            continue
        if any(abs(item["start"] - existing["start"]) < 180 for existing in deduped):
            continue
        deduped.append(item)
        if len(deduped) >= 12:
            break
    return deduped


def call_model(settings: Settings, evidence: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if not settings.dashscope_key:
        return None, "未找到 DASHSCOPE_API_KEY，使用可核对的规则分析；深度结论标记为待大模型复核。"
    system = """你是内部直播话术复盘分析师。只分析直播期间的话术与执行，不讨论短视频、投流或账号增长。必须根据本场证据重新判断，禁止套用上一场。使用痛点、塑品、活动机制、卡库存、逼单五环节，但不要强行分类。相关性不得写成严格因果，只能写时间关联、可能贡献或待复测假设。

严格遵守以下证据约束：
1. 所有时间、GMV、订单数、商品、流量和库存动作必须来自输入JSON，不得编造。
2. reusable_passages.quote必须逐字复制输入证据中的连续原话，不得改写、拼接不存在的句子或添加新数字。
3. 不得提出逐字稿中没有且无法核验的医学、生理或产品机理；可以分析主播说了什么，但不得把疗效或机理当成事实背书。
4. 不得建议虚构库存、后台踢单、销量、用户反馈、倒计时或任何无法证明的稀缺行为。只有输入证据真实出现的动作才可评价。
5. 强弱时段必须以输入中计算出的区间和波次排序为基础；不要用模糊的“前半场/后半场”替代具体时间。
6. 主播动作只可建议重排、缩短、复用或复测本场已有的可核验表达；如给出新写法，必须明确标为“建议改写（待验证）”。
7. 明确区分平台分钟成交口径、有效订单口径和已关闭订单；不得把无效订单算入话术后的成交。

返回严格JSON，字段为 headline, strong_period_analysis, weak_period_analysis, reusable_passages, cycle_recommendation, host_actions, hypotheses。每项尽量引用具体时间和原话。"""
    user = "请根据以下本场证据做深度复盘。JSON：\n" + json.dumps(evidence, ensure_ascii=False)
    body = json.dumps({"model": settings.text_model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0.2, "response_format": {"type": "json_object"}}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(settings.dashscope_url, data=body, headers={"Authorization": f"Bearer {settings.dashscope_key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
        return json.loads(content), "大模型深度分析完成"
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
        return None, f"大模型分析失败，已降级为规则分析：{exc}"


def build_review(sentences: list[dict[str, Any]], timeline: dict[str, Any], warnings: list[str], settings: Settings) -> dict[str, Any]:
    """Build a traffic-only review. Transaction fields are intentionally ignored."""
    duration = timeline["duration"]

    def summarize(start: float, end: float) -> dict[str, Any]:
        rows = [m for m in timeline["minutes"] if m.get("offset") is not None and start <= m["offset"] < end]
        ss = [s for s in sentences if s["end_seconds"] >= start and s["start_seconds"] < end]
        entrants = sum(r.get("viewers", 0) for r in rows)
        leavers = sum(r.get("leavers", 0) for r in rows)
        exposure = sum(r.get("exposure", 0) for r in rows)
        clicks = sum(r.get("product_clicks", 0) for r in rows)
        interactions = sum(r.get("interaction", 0) for r in rows)
        likes = sum(r.get("likes", 0) for r in rows)
        followers = sum(r.get("followers", 0) for r in rows)
        watch_values = [r.get("watch_seconds", 0) for r in rows if r.get("watch_seconds", 0) > 0]
        online_values = [r.get("online", 0) for r in rows]
        excerpt = "".join(s["text"] for s in ss[:10])[:700]
        return {
            "start": start, "end": end, "video_time": f"{hms(start)}–{hms(end)}",
            "entrants": round(entrants, 2), "leavers": round(leavers, 2), "net_flow": round(entrants-leavers, 2),
            "average_online": round(sum(online_values)/max(len(online_values), 1), 2), "peak_online": round(max(online_values or [0]), 2),
            "watch_seconds": round(sum(watch_values)/max(len(watch_values), 1), 2), "interaction": round(interactions, 2),
            "likes": round(likes, 2), "followers": round(followers, 2), "exposure": round(exposure, 2), "clicks": round(clicks, 2),
            "click_rate": round(clicks/exposure, 4) if exposure else 0, "excerpt": excerpt,
        }

    blocks = [summarize(x, min(x+600, duration)) for x in range(0, max(1, math.ceil(duration/600))*600, 600) if x < duration]
    for block in blocks:
        block["score"] = block["net_flow"] + block["watch_seconds"] + block["followers"]*8 + block["interaction"]*.3 + block["click_rate"]*200
    strong = sorted(blocks, key=lambda x: x["score"], reverse=True)[:3]
    weak = sorted(blocks, key=lambda x: x["score"])[:3]

    passages = []
    for block in blocks:
        if not block["excerpt"]:
            continue
        passages.append({"video_time": block["video_time"], "text": block["excerpt"], **{k:block[k] for k in ("entrants","leavers","net_flow","average_online","watch_seconds","interaction","followers","exposure","clicks","click_rate")}})
    evidence = {"session": {"duration": hms(duration)}, "strong_blocks": strong, "weak_blocks": weak, "all_blocks": blocks, "candidate_passages": passages, "limitations": warnings}

    traffic_system = """你是内部直播流量与话术分析师。只分析直播期间的话术与流量表现之间的关系，不得讨论GMV、成交、订单、销量或收入。根据输入中的进入、离开、净流入、实时在线、停留、互动、关注、商品曝光和点击，比较具体时间段的话术差异。不得把同期相关性写成确定因果。必须引用具体时间和输入中真实出现的连续原话，不得编造。输出严格JSON：headline, strong_period_analysis, weak_period_analysis, reusable_passages, cycle_recommendation, host_actions, hypotheses。strong/weak每项含time、analysis、action；reusable_passages每项含time、quote、why、usage、confidence；cycle_recommendation含range、reason、allocation。"""
    model = None
    model_note = "未配置Qwen，使用本地流量规则分析。"
    if settings.dashscope_key:
        body = json.dumps({"model": settings.text_model, "messages": [{"role":"system","content":traffic_system},{"role":"user","content":"请分析：\n"+json.dumps(evidence,ensure_ascii=False)}], "temperature":0.2, "response_format":{"type":"json_object"}}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(settings.dashscope_url,data=body,headers={"Authorization":f"Bearer {settings.dashscope_key}","Content-Type":"application/json"},method="POST")
        try:
            with urllib.request.urlopen(request,timeout=180) as response:
                payload=json.loads(response.read().decode("utf-8"))
            content=re.sub(r"^```(?:json)?|```$","",payload["choices"][0]["message"]["content"].strip(),flags=re.M).strip()
            model=json.loads(content); model_note="Qwen流量与话术深度分析完成。"
        except Exception as exc:
            model_note=f"Qwen分析失败，已使用本地流量规则：{exc}"
    warnings.append(model_note)

    def metric_text(b: dict[str, Any]) -> str:
        return f"进入{b['entrants']:.0f}、离开{b['leavers']:.0f}、净流入{b['net_flow']:+.0f}；平均在线{b['average_online']:.0f}，平均观看{b['watch_seconds']:.1f}秒；商品曝光{b['exposure']:.0f}、点击{b['clicks']:.0f}（{b['click_rate']:.1%}）。"

    fallback = {
        "headline": f"本场流量承接相对较好的窗口是{strong[0]['video_time'] if strong else '未识别'}；相对较弱的窗口是{weak[0]['video_time'] if weak else '未识别'}。判断仅基于流量与同期话术，不使用任何交易结果。",
        "strong_period_analysis": [{"time":b["video_time"],"analysis":metric_text(b)+"同期话术："+b["excerpt"][:220],"action":"保留该段的具体场景、可观察细节和清晰提问结构，并在相近流量下复测。"} for b in strong],
        "weak_period_analysis": [{"time":b["video_time"],"analysis":metric_text(b)+"同期话术："+b["excerpt"][:220],"action":"减少泛化形容和重复口令，用新的具体问题或证明重启一轮。"} for b in weak],
        "reusable_passages": [{"time":b["video_time"],"quote":b["excerpt"][:420],"why":metric_text(b),"usage":"复用原话的结构和信息顺序，具体表述仍需基于真实信息。","confidence":"中"} for b in strong],
        "cycle_recommendation":{"range":"6–8分钟","reason":"用较短循环持续给新进入用户提供新的场景、证明与行动入口，避免同一主题长时间重复。","allocation":"具体场景1分钟；个人证明1–1.5分钟；单一核心证明1.5–2分钟；互动答疑1分钟；明确行动0.5分钟；新人重启0.5–1分钟。"},
        "host_actions":["每轮先让新进入的人在一句话内判断‘是不是我’。","把泛化结果改成可观察细节，再解释原因。","每轮只讲一个核心证明，不连续堆概念。","库存和操作口令控制在45秒内，随后回到价值内容。","连续3分钟停留、在线或点击同步走弱时，立即换场景重启。"],
        "hypotheses":["所有结论均为话术与流量变化的同期关系，需要下一场按同一指标复测。"],
    }
    conclusions=json.loads(json.dumps(fallback,ensure_ascii=False))
    if isinstance(model,dict):
        for key,value in model.items():
            if value not in (None,"",[],{}): conclusions[key]=value
    for key in ("strong_period_analysis","weak_period_analysis","reusable_passages"):
        if not isinstance(conclusions.get(key),list): conclusions[key]=fallback[key]
    if not isinstance(conclusions.get("cycle_recommendation"),dict): conclusions["cycle_recommendation"]=fallback["cycle_recommendation"]
    # Quotes must be traceable to this transcript. Fall back to verified excerpts otherwise.
    transcript_all="".join(s["text"] for s in sentences)
    valid_quotes=[]
    for item in conclusions.get("reusable_passages",[]):
        if isinstance(item,dict):
            quote=str(item.get("quote") or "").strip()
            if quote and (quote in transcript_all or quote[:20] in transcript_all): valid_quotes.append(item)
    conclusions["reusable_passages"]=valid_quotes or fallback["reusable_passages"]
    return {"conclusions":conclusions,"blocks":blocks,"waves":blocks,"passages":passages,"evidence":evidence,"warnings":warnings}
