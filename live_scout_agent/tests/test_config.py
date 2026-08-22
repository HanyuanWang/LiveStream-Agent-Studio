import tempfile
import unittest
from pathlib import Path

from live_scout_agent.config import Settings


class SettingsTests(unittest.TestCase):
    def test_recorder_path_is_empty_by_default_and_reloads_after_save(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            scout = base / "live_scout_agent"
            breakdown = base / "live_breakdown_agent"
            scout.mkdir()
            breakdown.mkdir()
            settings = Settings.load(scout)

            self.assertIsNone(settings.current_quick_recorder_exe())

            first = base / "tools" / "recorder.exe"
            second = base / "other" / "recorder-v2.exe"
            (breakdown / ".env").write_text(f"QUICK_RECORDER_EXE={first}\n", encoding="utf-8")
            self.assertEqual(settings.current_quick_recorder_exe(), first)

            (breakdown / ".env").write_text(f"QUICK_RECORDER_EXE={second}\n", encoding="utf-8")
            self.assertEqual(settings.current_quick_recorder_exe(), second)


if __name__ == "__main__":
    unittest.main()
