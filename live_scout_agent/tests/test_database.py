import tempfile
import unittest
from pathlib import Path

from live_scout_agent.database import Database
from live_scout_agent.domain_parser import parse_theme_rules
from live_scout_agent.server import normalize_douyin_profile_url


class DatabaseTests(unittest.TestCase):
    def test_normalize_douyin_profile_url_from_share_text(self):
        value = normalize_douyin_profile_url(
            "复制打开抖音 https://www.douyin.com/user/MS4w.test?from=web 分享"
        )
        self.assertEqual(value, "https://www.douyin.com/user/MS4w.test")

    def test_reject_non_douyin_profile_url(self):
        with self.assertRaises(ValueError):
            normalize_douyin_profile_url("https://example.com/user/test")
    def test_theme_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "test.db")
            created = database.create_theme(parse_theme_rules("我关注女装，30万粉以下").to_dict())
            self.assertEqual(created["name"], "女装")
            self.assertEqual(created["max_followers"], 300_000)
            listed = database.list_themes()
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["candidate_count"], 0)

    def test_null_optional_text_is_saved_as_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "test.db")
            data = parse_theme_rules("我关注女装").to_dict()
            data["target_audience"] = None
            created = database.create_theme(data)
            self.assertEqual(created["target_audience"], "")

    def test_delete_theme_cascades_candidates_and_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "test.db")
            created = database.create_theme(parse_theme_rules("我关注女装").to_dict())
            import_id = database.create_import(created["id"], "test.csv", "test", 1, 1, [])
            database.upsert_candidates(
                created["id"],
                import_id,
                "test",
                [
                    {
                        "source_key": "creator-1",
                        "anchor_name": "测试达人",
                        "score": 10,
                    }
                ],
            )
            result = database.delete_theme(created["id"])
            self.assertEqual(result["deleted_candidates"], 1)
            self.assertEqual(result["deleted_imports"], 1)
            self.assertIsNone(database.get_theme(created["id"]))
            self.assertEqual(database.list_candidates(), [])

    def test_update_candidate_profile_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "test.db")
            theme = database.create_theme(parse_theme_rules("我关注女装").to_dict())
            import_id = database.create_import(theme["id"], "test.csv", "test", 1, 1, [])
            database.upsert_candidates(
                theme["id"],
                import_id,
                "test",
                [{"source_key": "creator-1", "anchor_name": "测试达人", "score": 10}],
            )
            candidate = database.list_candidates()[0]
            updated = database.update_candidate_profile_urls(
                {candidate["id"]: "https://www.douyin.com/user/example"}
            )
            self.assertEqual(updated, 1)
            self.assertEqual(
                database.list_candidates()[0]["profile_url"],
                "https://www.douyin.com/user/example",
            )


if __name__ == "__main__":
    unittest.main()
