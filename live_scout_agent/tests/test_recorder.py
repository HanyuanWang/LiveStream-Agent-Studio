import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from live_scout_agent.recorder import (
    _invoke_protocol,
    add_candidates_to_quick,
    write_quick_import_file,
)


class RecorderTests(unittest.TestCase):
    def test_write_quick_import_file(self):
        candidates = [
            {"anchor_name": "主播甲", "profile_url": "https://www.douyin.com/user/one"},
            {"anchor_name": "主播乙", "profile_url": ""},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path, missing = write_quick_import_file(candidates, Path(directory), "女装")
            self.assertIn("https://www.douyin.com/user/one", path.read_text(encoding="utf-8-sig"))
            self.assertEqual(missing, ["主播乙"])

    @patch("live_scout_agent.recorder._invoke_protocol")
    def test_add_candidates_uses_kdlive_protocol(self, invoke):
        candidates = [{"id": 7, "anchor_name": "主播甲", "profile_url": "https://www.douyin.com/user/a?x=1"}]
        added, missing = add_candidates_to_quick(candidates, Path("quick.exe"))
        self.assertEqual(added, [7])
        self.assertEqual(missing, [])
        uri = invoke.call_args.args[1]
        self.assertTrue(uri.startswith("kdlive://add?url="))
        self.assertIn("https%3A%2F%2Fwww.douyin.com", uri)

    @patch("live_scout_agent.recorder.subprocess.Popen")
    def test_invoke_protocol_launches_quick_with_uri(self, popen):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "quick.exe"
            executable.touch()
            _invoke_protocol(executable, "kdlive://start-monitor")
            popen.assert_called_once_with(
                [str(executable), "kdlive://start-monitor"],
                cwd=str(executable.parent),
            )


if __name__ == "__main__":
    unittest.main()
