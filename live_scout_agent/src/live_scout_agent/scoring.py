from __future__ import annotations

from typing import Any

from .importers import parse_number


def _percentiles(candidates: list[dict[str, Any]], key: str, reverse: bool = False) -> dict[int, float]:
    present = [(index, float(candidate[key])) for index, candidate in enumerate(candidates) if candidate.get(key) is not None]
    if not present:
        return {}
    present.sort(key=lambda item: item[1], reverse=reverse)
    if len(present) == 1:
        return {present[0][0]: 1.0}
    return {index: rank / (len(present) - 1) for rank, (index, _) in enumerate(present)} if reverse else {
        index: rank / (len(present) - 1) for rank, (index, _) in enumerate(present)
    }


def _high_score(percentiles: dict[int, float], index: int, missing: float = 0.35) -> float:
    return percentiles.get(index, missing)


def _low_score(percentiles: dict[int, float], index: int, missing: float = 0.4) -> float:
    return 1 - percentiles[index] if index in percentiles else missing


def _text_match(candidate: dict[str, Any], theme: dict[str, Any]) -> tuple[float, list[str], bool]:
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ["category", "title", "products", "account_type"]
    ).lower()
    includes = [str(value).lower() for value in theme.get("include_keywords", [])]
    excludes = [str(value).lower() for value in theme.get("exclude_keywords", [])]
    platform_terms = [str(theme.get("platform_category") or "").lower()] + [
        str(value).lower() for value in theme.get("subcategories", [])
    ]
    excluded = [term for term in excludes if term and term in text]
    if excluded:
        return 0.0, ["命中排除词：" + "、".join(excluded)], True
    include_hits = [term for term in includes if term and term in text]
    category_hits = [term for term in platform_terms if term and term != "待确认" and term in text]
    if include_hits:
        return 1.0, ["匹配主题词：" + "、".join(include_hits[:4])], False
    if category_hits:
        return 0.85, ["匹配榜单类目"], False
    if not text.strip() or not includes:
        return 0.65, ["缺少商品/类目字段，待复核"], False
    return 0.25, ["主题匹配较弱"], False


def score_candidates(candidates: list[dict[str, Any]], theme: dict[str, Any]) -> list[dict[str, Any]]:
    comparable_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        clone = dict(candidate)
        clone["_gmv_for_scoring"] = (
            candidate.get("estimated_gmv")
            if candidate.get("estimated_gmv") is not None
            else parse_number(candidate.get("estimated_gmv_text"))
        )
        clone["_sales_for_scoring"] = (
            candidate.get("sales_volume")
            if candidate.get("sales_volume") is not None
            else parse_number(candidate.get("sales_volume_text"))
        )
        comparable_candidates.append(clone)

    gpm_pct = _percentiles(comparable_candidates, "gpm")
    uv_pct = _percentiles(comparable_candidates, "uv_value")
    gmv_pct = _percentiles(comparable_candidates, "_gmv_for_scoring")
    sales_pct = _percentiles(comparable_candidates, "_sales_for_scoring")
    follower_pct = _percentiles(comparable_candidates, "followers")
    gmv_per_hour_values: list[dict[str, Any]] = []
    for candidate in comparable_candidates:
        clone = dict(candidate)
        if candidate.get("_gmv_for_scoring") is not None and candidate.get("duration_hours"):
            clone["gmv_per_hour"] = float(candidate["_gmv_for_scoring"]) / max(float(candidate["duration_hours"]), 0.1)
        else:
            clone["gmv_per_hour"] = None
        gmv_per_hour_values.append(clone)
    gmv_hour_pct = _percentiles(gmv_per_hour_values, "gmv_per_hour")

    scored: list[dict[str, Any]] = []
    for index, candidate in enumerate(comparable_candidates):
        reasons: list[str] = []
        efficiency_metrics = [
            _high_score(gpm_pct, index) if candidate.get("gpm") is not None else None,
            _high_score(uv_pct, index) if candidate.get("uv_value") is not None else None,
            _high_score(gmv_hour_pct, index) if gmv_per_hour_values[index].get("gmv_per_hour") is not None else None,
        ]
        efficiency_present = [value for value in efficiency_metrics if value is not None]
        efficiency = sum(efficiency_present) / len(efficiency_present) if efficiency_present else 0.35
        sales_metrics = [
            _high_score(gmv_pct, index) if candidate.get("_gmv_for_scoring") is not None else None,
            _high_score(sales_pct, index) if candidate.get("_sales_for_scoring") is not None else None,
        ]
        sales_present = [value for value in sales_metrics if value is not None]
        sales = sum(sales_present) / len(sales_present) if sales_present else 0.35
        low_fan = _low_score(follower_pct, index)
        max_followers = theme.get("max_followers")
        followers = candidate.get("followers")
        if max_followers and followers is not None:
            absolute_low_fan = max(0.0, min(1.0, 1 - float(followers) / float(max_followers)))
            low_fan = absolute_low_fan if len(follower_pct) <= 1 else (low_fan + absolute_low_fan) / 2
        sessions = candidate.get("sessions_7d")
        stability = float(candidate.get("stability")) if candidate.get("stability") is not None else (
            min(float(sessions) / 5, 1.0) if sessions is not None else 0.45
        )
        if stability > 1:
            stability /= 100
        theme_match, theme_reasons, hard_excluded = _text_match(candidate, theme)
        reasons.extend(theme_reasons)
        score = 100 * (0.30 * efficiency + 0.25 * sales + 0.20 * low_fan + 0.15 * stability + 0.10 * theme_match)

        status = "candidate"
        if max_followers and followers is not None and float(followers) > float(max_followers):
            score *= 0.55
            reasons.append("超过粉丝上限")
        elif followers is not None and follower_pct.get(index, 1) <= 0.25:
            reasons.append("同批次低粉")
        if efficiency >= 0.75:
            reasons.append("成交效率靠前")
        if sales >= 0.75:
            reasons.append("销售表现靠前")
        if stability >= 0.8:
            reasons.append("近期开播稳定")
        if hard_excluded:
            score = min(score, 20)
            status = "rejected"
        result = dict(candidate)
        result.pop("_gmv_for_scoring", None)
        result.pop("_sales_for_scoring", None)
        result.update(score=round(score, 1), status=status, reasons=list(dict.fromkeys(reasons)))
        scored.append(result)
    return sorted(scored, key=lambda item: item["score"], reverse=True)
