import tempfile
import unittest
from pathlib import Path

from live_scout_agent.chanmama import (
    DEFAULT_STATE,
    read_state,
    resolve_chanmama_category,
    write_state,
)


class ChanmamaStateTests(unittest.TestCase):
    def test_missing_state_uses_safe_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            state = read_state(Path(directory) / "state.json")
        self.assertEqual(state["phase"], "not_configured")
        self.assertFalse(state["logged_in"])
        self.assertFalse(state["busy"])

    def test_state_roundtrip_preserves_login(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            write_state(path, {**DEFAULT_STATE, "phase": "ready", "logged_in": True})
            state = read_state(path)
        self.assertEqual(state["phase"], "ready")
        self.assertTrue(state["logged_in"])
        self.assertIn("updated_at", state)

    def test_broken_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("{broken", encoding="utf-8")
            state = read_state(path)
        self.assertEqual(state["phase"], "error")
        self.assertFalse(state["logged_in"])

    def test_theme_maps_to_chanmama_category(self):
        self.assertEqual(
            resolve_chanmama_category(
                {
                    "name": "中高端女装",
                    "description": "寻找低粉高转化的女装主播",
                    "platform_category": "服饰鞋包",
                    "subcategories": ["女装"],
                }
            ),
            "服饰内衣",
        )
        self.assertEqual(
            resolve_chanmama_category(
                {
                    "name": "保健品",
                    "description": "滋补保健",
                    "platform_category": "食品饮料",
                    "subcategories": ["膳食营养补充"],
                }
            ),
            "医药保健",
        )


if __name__ == "__main__":
    unittest.main()
