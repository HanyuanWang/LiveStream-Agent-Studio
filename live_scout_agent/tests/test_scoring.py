import unittest

from live_scout_agent.scoring import score_candidates


class ScoringTests(unittest.TestCase):
    def test_low_fan_high_efficiency_ranks_first(self):
        theme = {
            "platform_category": "服饰鞋包",
            "subcategories": ["女装"],
            "include_keywords": ["女装", "通勤"],
            "exclude_keywords": ["童装"],
            "max_followers": 300_000,
        }
        candidates = [
            {"anchor_name": "低粉强转化", "followers": 80_000, "category": "女装", "estimated_gmv": 500_000, "gpm": 2500, "uv_value": 4.2, "sessions_7d": 5},
            {"anchor_name": "高粉普通", "followers": 900_000, "category": "女装", "estimated_gmv": 600_000, "gpm": 800, "uv_value": 1.1, "sessions_7d": 5},
            {"anchor_name": "错误类目", "followers": 30_000, "category": "童装", "estimated_gmv": 900_000, "gpm": 3000, "uv_value": 5.0, "sessions_7d": 5},
        ]
        result = score_candidates(candidates, theme)
        self.assertEqual(result[0]["anchor_name"], "低粉强转化")
        excluded = next(item for item in result if item["anchor_name"] == "错误类目")
        self.assertEqual(excluded["status"], "rejected")
        self.assertLessEqual(excluded["score"], 20)


if __name__ == "__main__":
    unittest.main()

