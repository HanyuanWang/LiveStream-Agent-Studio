from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Any

from .http_client import request_json


CATEGORY_MAP: dict[str, tuple[str, list[str]]] = {
    "中高端女装": ("服饰鞋包", ["女装", "连衣裙", "通勤装"]),
    "女装": ("服饰鞋包", ["女装"]),
    "男装": ("服饰鞋包", ["男装"]),
    "内衣": ("服饰鞋包", ["内衣"]),
    "鞋靴箱包": ("服饰鞋包", ["鞋靴", "箱包"]),
    "美妆护肤": ("美妆", ["护肤", "彩妆"]),
    "护肤": ("美妆", ["护肤"]),
    "彩妆": ("美妆", ["彩妆"]),
    "保健品": ("食品饮料", ["滋补保健", "膳食营养补充"]),
    "滋补": ("食品饮料", ["滋补保健"]),
    "食品饮料": ("食品饮料", ["食品", "饮料"]),
    "珠宝文玩": ("珠宝文玩", ["珠宝", "文玩"]),
    "家居百货": ("家居生活", ["家居", "百货"]),
    "母婴": ("母婴", ["母婴用品"]),
}


@dataclass
class ThemeDraft:
    name: str
    description: str
    platform_category: str
    subcategories: list[str]
    include_keywords: list[str]
    exclude_keywords: list[str]
    min_price: float | None
    max_price: float | None
    max_followers: int | None
    account_types: list[str]
    preferred_traits: list[str]
    target_audience: str
    daily_limit: int = 5
    trial_recordings: int = 2
    auto_add: bool = False
    parser: str = "rules"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _split_terms(text: str) -> list[str]:
    return _unique(re.split(r"[、，,；;和及]", text.strip("。；;，,")))


def _number_with_unit(value: str, unit: str | None) -> int:
    number = float(value)
    if unit and unit.lower() in {"万", "w"}:
        number *= 10_000
    return int(number)


def parse_theme_rules(description: str) -> ThemeDraft:
    text = description.strip()
    matched_name = next((name for name in CATEGORY_MAP if name in text), "自定义领域")
    platform_category, subcategories = CATEGORY_MAP.get(matched_name, ("待确认", []))

    price = re.search(r"(?:价格|客单价|价位)?\s*(\d+(?:\.\d+)?)\s*[～~—\-至到]\s*(\d+(?:\.\d+)?)\s*元", text)
    min_price = float(price.group(1)) if price else None
    max_price = float(price.group(2)) if price else None

    follower = re.search(
        r"(?:粉丝?\s*)?(\d+(?:\.\d+)?)\s*(万|w)?\s*(?:粉(?:丝)?)?\s*(?:以内|以下|为上限)",
        text,
        re.I,
    )
    max_followers = _number_with_unit(follower.group(1), follower.group(2)) if follower else None

    exclude_keywords: list[str] = []
    for match in re.finditer(r"(?:不要|排除|不包含|剔除)([^。；;]+)", text):
        exclude_keywords.extend(_split_terms(match.group(1)))

    include_keywords = list(subcategories)
    keyword_match = re.search(r"(?:主要是|包括|包含|例如|比如)([^。；;]+)", text)
    if keyword_match:
        include_keywords.extend(_split_terms(keyword_match.group(1)))
    include_keywords = [item for item in _unique(include_keywords) if item not in exclude_keywords]

    account_types: list[str] = []
    for account_type in ["真人主播", "达人直播", "品牌自播", "店铺直播", "知识讲解型"]:
        if account_type in text or account_type.replace("直播", "") in text:
            account_types.append(account_type)
    if not account_types:
        account_types = ["真人主播"]

    preferred_traits: list[str] = []
    for trait in ["有人设", "低粉高转化", "强互动", "知识讲解", "强成交", "自然流量"]:
        if trait in text or trait.replace("强", "") in text:
            preferred_traits.append(trait)
    if "粉" in text and ("少" in text or "低" in text):
        preferred_traits.append("低粉高转化")

    audience = ""
    audience_match = re.search(r"(?:面向|人群是|目标人群)([^。；;]+)", text)
    if audience_match:
        audience = audience_match.group(1).strip()

    return ThemeDraft(
        name=matched_name,
        description=text,
        platform_category=platform_category,
        subcategories=_unique(subcategories),
        include_keywords=_unique(include_keywords),
        exclude_keywords=_unique(exclude_keywords),
        min_price=min_price,
        max_price=max_price,
        max_followers=max_followers,
        account_types=_unique(account_types),
        preferred_traits=_unique(preferred_traits),
        target_audience=audience,
    )


def _clean_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(cleaned)


def parse_theme_with_qwen(
    description: str,
    api_key: str,
    base_url: str,
    model: str,
) -> ThemeDraft:
    fallback = parse_theme_rules(description)
    if not api_key:
        return fallback
    schema = {
        "name": "中高端女装",
        "description": description,
        "platform_category": "服饰鞋包",
        "subcategories": ["女装"],
        "include_keywords": ["通勤", "连衣裙"],
        "exclude_keywords": ["童装", "内衣"],
        "min_price": 200,
        "max_price": 800,
        "max_followers": 300000,
        "account_types": ["真人主播", "达人直播"],
        "preferred_traits": ["有人设", "低粉高转化"],
        "target_audience": "30至45岁女性",
        "daily_limit": 5,
        "trial_recordings": 2,
        "auto_add": False,
    }
    response = request_json(
        "POST",
        f"{base_url}/compatible-mode/v1/chat/completions",
        {"Authorization": f"Bearer {api_key}"},
        {
            "model": model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "你是直播带货主播发现Agent。把用户自然语言转换为严格JSON筛选条件，不补充用户没有表达的价格和粉丝限制。",
                },
                {
                    "role": "user",
                    "content": "输出结构必须与示例一致；数组不能为空时才填写，无法判断用空数组或null。示例："
                    + json.dumps(schema, ensure_ascii=False)
                    + "\n用户描述："
                    + description,
                },
            ],
        },
    )
    parsed = _clean_json(response["choices"][0]["message"]["content"])
    allowed = ThemeDraft.__dataclass_fields__
    merged = {**fallback.to_dict(), **{key: value for key, value in parsed.items() if key in allowed}}
    merged["description"] = description.strip()
    merged["parser"] = "qwen"
    for key in ["subcategories", "include_keywords", "exclude_keywords", "account_types", "preferred_traits"]:
        merged[key] = _unique([str(value) for value in (merged.get(key) or [])])
    merged["target_audience"] = str(merged.get("target_audience") or "")
    merged["daily_limit"] = int(merged.get("daily_limit") or fallback.daily_limit)
    merged["trial_recordings"] = int(merged.get("trial_recordings") or fallback.trial_recordings)
    merged["auto_add"] = bool(merged.get("auto_add"))
    return ThemeDraft(**merged)
