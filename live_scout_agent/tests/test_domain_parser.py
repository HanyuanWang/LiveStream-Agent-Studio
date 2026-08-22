import unittest

from live_scout_agent.domain_parser import parse_theme_rules


class ThemeParserTests(unittest.TestCase):
    def test_parse_womenswear_description(self):
        draft = parse_theme_rules(
            "我关注中高端女装，主要面向30～45岁女性，客单价200～800元。"
            "不要童装、内衣和低价清仓号，优先找30万粉以下、真人出镜、有人设的主播。"
        )
        self.assertEqual(draft.name, "中高端女装")
        self.assertEqual(draft.platform_category, "服饰鞋包")
        self.assertEqual(draft.min_price, 200)
        self.assertEqual(draft.max_price, 800)
        self.assertEqual(draft.max_followers, 300_000)
        self.assertIn("童装", draft.exclude_keywords)
        self.assertIn("有人设", draft.preferred_traits)

    def test_parse_health_theme(self):
        draft = parse_theme_rules("我关注保健品，粉丝10万以下，不要医疗器械和药品")
        self.assertEqual(draft.name, "保健品")
        self.assertIn("滋补保健", draft.subcategories)
        self.assertEqual(draft.max_followers, 100_000)
        self.assertIn("医疗器械", draft.exclude_keywords)


if __name__ == "__main__":
    unittest.main()

