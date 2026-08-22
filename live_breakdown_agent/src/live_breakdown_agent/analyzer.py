from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .http import request_json
from .models import EventRow, TranscriptSegment, validate_event_rows


SYSTEM_PROMPT = """你是直播逐字稿拆解 Agent。只能依据给定的完整逐字稿工作，不得补写主播没说过的话。
输出用于三列表格：时间戳、事件、逐字稿。事件需要识别第N品/品名，以及做人设、互动、痛点、卖点、价格、上链接、库存、催单、返场、转品等动作。
逐字稿必须忠实保留原意；事件切分应覆盖输入片段，时间戳为秒。只返回合法 JSON。"""


def chunk_segments(segments: list[TranscriptSegment], max_chars: int = 36_000, max_seconds: int = 2700) -> list[list[TranscriptSegment]]:
    """只在完整转写结束后分块，控制文本模型输入规模。"""
    chunks: list[list[TranscriptSegment]] = []
    current: list[TranscriptSegment] = []
    char_count = 0
    chunk_start = 0.0
    for segment in segments:
        if not current:
            chunk_start = segment.start
        would_overflow = current and (char_count + len(segment.text) > max_chars or segment.end - chunk_start > max_seconds)
        if would_overflow:
            chunks.append(current)
            current = []
            char_count = 0
            chunk_start = segment.start
        current.append(segment)
        char_count += len(segment.text)
    if current:
        chunks.append(current)
    return chunks


def _summarize_events(events: list[str]) -> str:
    unique_events = list(dict.fromkeys(event.strip() for event in events if event.strip()))
    prefixes: list[str] = []
    actions: list[str] = []
    for event in unique_events:
        if "｜" in event:
            prefix, action = event.split("｜", 1)
            if prefix not in prefixes:
                prefixes.append(prefix)
            for item in action.split("+"):
                item = item.strip()
                if item and item not in actions:
                    actions.append(item)
        elif event not in prefixes:
            prefixes.append(event)
    if len(prefixes) == 1:
        return prefixes[0] + (f"｜{'+'.join(actions)}" if actions else "")
    return "；".join(unique_events)


def coarsen_event_rows(
    rows: list[EventRow],
    min_seconds: int = 60,
    max_seconds: int = 300,
    allow_oversized_tail: bool = False,
    allow_short: bool = False,
) -> list[EventRow]:
    """把模型的细粒度动作合并为 1–5 分钟的复盘段落。"""
    if not rows:
        return []
    merged: list[EventRow] = []
    pending: list[EventRow] = []

    def emit(group: list[EventRow]) -> None:
        merged.append(EventRow(
            group[0].start,
            group[-1].end,
            _summarize_events([row.event for row in group]),
            "".join(row.transcript for row in group),
            any(row.is_key_event for row in group),
        ))

    for row in rows:
        if pending and row.end - pending[0].start > max_seconds:
            emit(pending)
            pending = []
        pending.append(row)
        if pending[-1].end - pending[0].start >= min_seconds:
            emit(pending)
            pending = []
    if pending:
        pending_duration = pending[-1].end - pending[0].start
        if merged and (pending_duration < min_seconds or pending[-1].end - merged[-1].start <= max_seconds):
            previous = merged.pop()
            emit([previous, *pending])
        else:
            emit(pending)

    # ASR 相邻句偶尔会有亚秒级重叠；对宏观事件段统一到下一整秒，避免 Excel 显示重叠。
    aligned: list[EventRow] = []
    for row in merged:
        start = row.start
        if aligned:
            displayed_boundary = math.ceil(aligned[-1].end)
            if math.floor(start) < displayed_boundary:
                start = min(row.end - 0.001, float(displayed_boundary))
        aligned.append(EventRow(start, row.end, row.event, row.transcript, row.is_key_event))
    merged = aligned

    for row in merged:
        duration = row.end - row.start
        if duration > max_seconds + 0.001 and not allow_oversized_tail:
            raise ValueError(f"事件段超过 {max_seconds} 秒，需要进一步按原句切分: {row.timestamp}")
        # 边界为消除 ASR 亚秒重叠会向下一整秒对齐。内部浮点时长可能因此
        # 少于下限不到 1 秒，但最终 Excel 时间戳仍完整覆盖 60 秒；按最终
        # 展示秒数校验，避免把合法的 00:59:50-01:00:50 误判为不足一分钟。
        displayed_duration = math.ceil(row.end) - math.floor(row.start)
        if len(merged) > 1 and displayed_duration < min_seconds and not allow_short:
            raise ValueError(f"事件段不足 {min_seconds} 秒，无法满足合并约束: {row.timestamp}")
    return merged


def split_long_event_rows(rows: list[EventRow], segments: list[TranscriptSegment], max_seconds: int = 300) -> list[EventRow]:
    """在 ASR 原句边界切开超过上限的模型事件段。"""
    result: list[EventRow] = []
    for row in rows:
        duration = row.end - row.start
        if duration <= max_seconds:
            result.append(row)
            continue
        relevant = [segment for segment in segments if segment.end > row.start and segment.start < row.end]
        if not relevant:
            raise ValueError(f"长事件段找不到对应原句: {row.timestamp}")
        part_count = max(2, math.ceil(duration / max_seconds))
        buckets: list[list[TranscriptSegment]] = [[] for _ in range(part_count)]
        for segment in relevant:
            midpoint = (segment.start + segment.end) / 2
            ratio = min(0.999999, max(0.0, (midpoint - row.start) / duration))
            buckets[min(part_count - 1, int(ratio * part_count))].append(segment)
        non_empty = [bucket for bucket in buckets if bucket]
        for bucket in non_empty:
            result.append(EventRow(
                bucket[0].start,
                bucket[-1].end,
                row.event,
                "".join(segment.text for segment in bucket),
                row.is_key_event,
            ))
    return result


def rebalance_event_rows(
    rows: list[EventRow],
    segments: list[TranscriptSegment],
    min_seconds: int = 60,
    max_seconds: int = 300,
) -> list[EventRow]:
    """合并任意内部短段，并在原始 ASR 句子边界重新拆分超长段。"""
    working = list(rows)
    max_rounds = max(4, len(working) * 2)
    for _ in range(max_rounds):
        working = split_long_event_rows(working, segments, max_seconds)

        aligned: list[EventRow] = []
        for row in working:
            start = row.start
            if aligned:
                displayed_boundary = math.ceil(aligned[-1].end)
                if math.floor(start) < displayed_boundary:
                    start = min(row.end - 0.001, float(displayed_boundary))
            aligned.append(EventRow(start, row.end, row.event, row.transcript, row.is_key_event))
        working = aligned

        short_index = next((
            index for index, row in enumerate(working)
            if len(working) > 1 and math.ceil(row.end) - math.floor(row.start) < min_seconds
        ), None)
        if short_index is None:
            for row in working:
                if row.end - row.start > max_seconds + 0.001:
                    raise ValueError(f"事件段超过 {max_seconds} 秒: {row.timestamp}")
            return working

        neighbor_options: list[tuple[float, int, int]] = []
        if short_index > 0:
            neighbor_options.append((
                working[short_index].end - working[short_index - 1].start,
                short_index - 1,
                short_index,
            ))
        if short_index + 1 < len(working):
            neighbor_options.append((
                working[short_index + 1].end - working[short_index].start,
                short_index,
                short_index + 1,
            ))
        _, left, right = min(neighbor_options, key=lambda item: item[0])
        pair = working[left : right + 1]
        combined = EventRow(
            pair[0].start,
            pair[-1].end,
            _summarize_events([row.event for row in pair]),
            "".join(row.transcript for row in pair),
            any(row.is_key_event for row in pair),
        )
        working[left : right + 1] = [combined]
    raise ValueError("事件段重新平衡未收敛")


PRODUCT_NUMBER_RE = re.compile(r"第\s*(\d+)\s*品-")


def renumber_products_by_first_event(rows: list[EventRow], products: list[dict[str, Any]]) -> tuple[list[EventRow], list[dict[str, Any]]]:
    """按商品在最终时间轴第一次实际出现的顺序强制连续编号。"""
    number_map: dict[int, int] = {}
    next_number = 1
    for row in rows:
        for match in PRODUCT_NUMBER_RE.finditer(row.event):
            old_number = int(match.group(1))
            if old_number not in number_map:
                number_map[old_number] = next_number
                next_number += 1

    def replace_number(match: re.Match[str]) -> str:
        old_number = int(match.group(1))
        if old_number not in number_map:
            number_map[old_number] = len(number_map) + 1
        return f"第{number_map[old_number]}品-"

    renumbered_rows = [
        EventRow(row.start, row.end, PRODUCT_NUMBER_RE.sub(replace_number, row.event), row.transcript, row.is_key_event)
        for row in rows
    ]

    renumbered_products: list[dict[str, Any]] = []
    referenced_old_numbers = set(number_map)
    for product in products:
        product_copy = dict(product)
        try:
            old_number = int(product_copy.get("number"))
        except (TypeError, ValueError):
            continue
        if old_number in number_map:
            product_copy["number"] = number_map[old_number]
            renumbered_products.append(product_copy)
    for product in products:
        product_copy = dict(product)
        try:
            old_number = int(product_copy.get("number"))
        except (TypeError, ValueError):
            continue
        if old_number not in referenced_old_numbers:
            product_copy["number"] = next_number
            next_number += 1
            renumbered_products.append(product_copy)
    renumbered_products.sort(key=lambda item: int(item["number"]))
    return renumbered_rows, renumbered_products


class QwenAnalyzer:
    def __init__(self, api_key: str, base_url: str, model: str, cache_dir: Path | None = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.usage_records: list[dict[str, Any]] = []
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _chat_json(self, messages: list[dict[str, str]], temperature: float = 0.1, cache_key: str = "") -> Any:
        cache_path = self.cache_dir / f"{cache_key}.json" if self.cache_dir and cache_key else None
        if cache_path and cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            usage = dict(cached.get("usage", {}))
            usage["cache_key"] = cache_key
            usage["from_cache"] = True
            self.usage_records.append(usage)
            return cached["result"]
        data = request_json(
            "POST",
            f"{self.base_url}/compatible-mode/v1/chat/completions",
            {"Authorization": f"Bearer {self.api_key}"},
            {"model": self.model, "messages": messages, "temperature": temperature, "response_format": {"type": "json_object"}},
            timeout=180,
        )
        usage = {"model": self.model, **data.get("usage", {}), "cache_key": cache_key, "from_cache": False}
        self.usage_records.append(usage)
        content = data["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        result = json.loads(content)
        if cache_path:
            cache_path.write_text(json.dumps({"usage": usage, "result": result}, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    def build_product_registry(self, segments: list[TranscriptSegment]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for chunk_index, chunk in enumerate(chunk_segments(segments)):
            payload = [s.to_dict() for s in chunk]
            result = self._chat_json([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "完整直播已经转写完成；这是其中一段。只提取本段明确出现的商品候选，不要自行连续编号。返回 {\"products\":[{\"name\":\"...\",\"aliases\":[\"...\"],\"first_start\":0}]}。片段：" + json.dumps(payload, ensure_ascii=False)},
            ], cache_key=f"product_candidate_{chunk_index:03d}")
            candidates.extend(result.get("products", []))
        if not candidates:
            return []
        merged = self._chat_json([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "合并同一商品的别名，按 first_start 从早到晚建立整场直播的唯一商品编号。只返回 {\"products\":[{\"number\":1,\"name\":\"...\",\"aliases\":[\"...\"],\"first_start\":0}]}。候选：" + json.dumps(candidates, ensure_ascii=False)},
        ], cache_key="product_merge")
        return merged.get("products", [])

    def analyze(self, segments: list[TranscriptSegment], products: list[dict[str, Any]], min_event_seconds: int = 60, max_event_seconds: int = 300) -> list[EventRow]:
        rows: list[EventRow] = []
        for chunk_index, chunk in enumerate(chunk_segments(segments)):
            indexed = [{"index": index, **segment.to_dict()} for index, segment in enumerate(chunk)]
            result = self._chat_json([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"依据整场全局商品表切分本段事件。每个输入句子必须且只能归入一个事件，按连续句子索引返回；不要返回逐字稿文本。事件段尽量保持 {min_event_seconds}–{max_event_seconds} 秒，同一商品一分钟内的人设、卖点、价格、库存、催单等动作合并为复合事件。返回 {{\"rows\":[{{\"start_index\":0,\"end_index\":3,\"event\":\"第1品-品名｜人设+卖点+价格\",\"is_key_event\":false}}]}}。商品表：" + json.dumps(products, ensure_ascii=False) + "\n带索引片段：" + json.dumps(indexed, ensure_ascii=False)},
            ], cache_key=f"events_{chunk_index:03d}")
            cursor = 0
            raw_rows = sorted(result.get("rows", []), key=lambda x: int(x.get("start_index", 0)))
            for raw in raw_rows:
                requested_start = int(raw.get("start_index", cursor))
                if requested_start > cursor:
                    gap = chunk[cursor:min(requested_start, len(chunk))]
                    if gap:
                        rows.append(EventRow(gap[0].start, gap[-1].end, "未分类｜待复核", "".join(x.text for x in gap)))
                    cursor = requested_start
                start_index = max(cursor, requested_start)
                end_index = min(len(chunk) - 1, int(raw.get("end_index", start_index)))
                if start_index > end_index:
                    continue
                selected = chunk[start_index : end_index + 1]
                rows.append(EventRow(
                    selected[0].start,
                    selected[-1].end,
                    str(raw.get("event", "未分类｜直播讲解")),
                    "".join(segment.text for segment in selected),
                    bool(raw.get("is_key_event", False)),
                ))
                cursor = end_index + 1
            if cursor < len(chunk):
                selected = chunk[cursor:]
                rows.append(EventRow(selected[0].start, selected[-1].end, "未分类｜待复核", "".join(x.text for x in selected)))
        rows = split_long_event_rows(rows, segments, max_event_seconds)
        # 结尾不足一分钟时，先与上一段合并，再依据原始 ASR 句子边界重新均衡
        # 切开；这样既不丢失尾段，也能保持每段 1–5 分钟。
        rows = coarsen_event_rows(
            rows,
            min_event_seconds,
            max_event_seconds,
            allow_oversized_tail=True,
            allow_short=True,
        )
        rows = rebalance_event_rows(rows, segments, min_event_seconds, max_event_seconds)
        validate_event_rows(rows)
        return rows
