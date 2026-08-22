import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from live_scout_agent.chanmama import ChanmamaManager, read_state, write_state
from live_scout_agent.config import Settings


class ChanmamaStateTests(unittest.TestCase):
    @staticmethod
    def make_settings(root: Path) -> Settings:
        workspace = root / "workspace"
        chanmama = workspace / "chanmama"
        chanmama.mkdir(parents=True)
        return Settings(
            project_dir=root,
            workspace_dir=workspace,
            database_path=workspace / "test.db",
            web_dir=root / "web",
            host="127.0.0.1",
            port=8765,
            dashscope_api_key="",
            dashscope_base_url="https://example.test",
            text_model="qwen-plus",
            breakdown_project_dir=root / "breakdown",
            quick_recorder_exe=root / "quick.exe",
            chanmama_profile_dir=chanmama / "profile",
            chanmama_download_dir=chanmama / "downloads",
            chanmama_state_path=chanmama / "state.json",
            chanmama_start_url="https://example.test",
            report_dir=workspace / "reports",
            recording_dir=root / "recordings",
            relay_dir=workspace / "relay",
        )

    def test_stale_stopping_state_is_reconciled_on_status(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = self.make_settings(Path(directory))
            write_state(
                settings.chanmama_state_path,
                {
                    "phase": "stopping",
                    "message": "正在关闭蝉妈妈专用浏览器",
                    "busy": True,
                    "logged_in": False,
                    "mode": "external_login",
                    "page_title": "蝉妈妈专用登录窗口",
                },
            )

            state = ChanmamaManager(settings).status()

            self.assertFalse(state["busy"])
            self.assertEqual(state["phase"], "not_configured")
            self.assertEqual(state["page_title"], "")
            self.assertEqual(read_state(settings.chanmama_state_path)["mode"], "")

    def test_cancel_external_login_returns_to_idle_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = self.make_settings(Path(directory))
            write_state(
                settings.chanmama_state_path,
                {
                    "phase": "waiting_for_login",
                    "busy": True,
                    "logged_in": False,
                    "mode": "external_login",
                },
            )

            state = ChanmamaManager(settings).stop()

            self.assertFalse(state["busy"])
            self.assertEqual(state["phase"], "not_configured")

    def test_login_chrome_is_launched_without_a_console_window(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = self.make_settings(Path(directory))
            manager = ChanmamaManager(settings)
            process = Mock(pid=1234)
            with (
                patch("live_scout_agent.chanmama.Path.is_file", return_value=True),
                patch("live_scout_agent.chanmama.subprocess.Popen", return_value=process) as popen,
            ):
                manager._launch_login_chrome()

            arguments, options = popen.call_args
            self.assertIn("chrome.exe", str(arguments[0][0]).lower())
            self.assertEqual(
                options["creationflags"],
                getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0),
            )
            self.assertEqual(options["stdin"], __import__("subprocess").DEVNULL)


if __name__ == "__main__":
    unittest.main()
