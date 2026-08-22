import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from live_scout_agent.config import Settings
from live_scout_agent.database import Database
from live_scout_agent.domain_parser import parse_theme_rules
from live_scout_agent.relay import JOB_KIND, RecordingRelay, normalize_anchor


class RelayTests(unittest.TestCase):
    @staticmethod
    def make_settings(root: Path, recording_dir: Path) -> Settings:
        workspace = root / "workspace"
        relay_dir = workspace / "relay"
        relay_dir.mkdir(parents=True)
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
            chanmama_profile_dir=workspace / "chanmama" / "profile",
            chanmama_download_dir=workspace / "chanmama" / "downloads",
            chanmama_state_path=workspace / "chanmama" / "state.json",
            chanmama_start_url="https://example.test",
            report_dir=workspace / "reports",
            recording_dir=recording_dir,
            relay_dir=relay_dir,
        )

    def test_normalize_and_match_quick_folder_name(self):
        candidate = {"id": 1, "anchor_name": "斐萃S-雌马酚全方位更年期呵护"}
        path = Path(
            r"C:\录屏\2026年07月27日\斐萃S雌马酚全方位更年期呵护"
            r"\斐萃S雌马酚全方位更年期呵护20260727170413.ts"
        )
        self.assertEqual(normalize_anchor("斐萃S-雌马酚"), "斐萃s雌马酚")
        self.assertEqual(RecordingRelay._match_candidate(path, [candidate]), candidate)

    def test_auto_breakdown_and_job_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "test.db")
            theme = database.create_theme(parse_theme_rules("我关注保健品").to_dict())
            import_id = database.create_import(theme["id"], "test.csv", "test", 1, 1, [])
            database.upsert_candidates(
                theme["id"],
                import_id,
                "test",
                [{"source_key": "creator-1", "anchor_name": "测试主播", "score": 10}],
            )
            candidate = database.list_candidates()[0]
            self.assertEqual(
                database.set_candidate_auto_breakdown([candidate["id"]], True),
                1,
            )
            self.assertTrue(database.list_auto_breakdown_candidates()[0]["auto_breakdown"])
            source_path = str(Path(directory) / "test.ts")
            job_id = database.create_integration_job(
                candidate["id"],
                JOB_KIND,
                "queued",
                {"source_path": source_path},
                "等待处理",
            )
            found = database.find_integration_job(JOB_KIND, source_path)
            self.assertEqual(found["id"], job_id)
            database.update_integration_job(
                job_id,
                "completed",
                "完成",
                {"output_path": "result.xlsx"},
            )
            updated = database.get_integration_job(job_id)
            self.assertEqual(updated["status"], "completed")
            self.assertEqual(updated["payload"]["output_path"], "result.xlsx")

    def test_new_stable_recording_is_queued_but_history_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recording_dir = root / "recordings"
            anchor_dir = recording_dir / "2026年07月28日" / "测试主播"
            anchor_dir.mkdir(parents=True)
            database = Database(root / "workspace" / "test.db")
            theme = database.create_theme(parse_theme_rules("我关注保健品").to_dict())
            import_id = database.create_import(theme["id"], "test.csv", "test", 1, 1, [])
            database.upsert_candidates(
                theme["id"],
                import_id,
                "test",
                [{"source_key": "creator-1", "anchor_name": "测试主播", "score": 10}],
            )
            candidate = database.list_candidates()[0]
            database.set_candidate_auto_breakdown([candidate["id"]], True)
            relay = RecordingRelay(self.make_settings(root, recording_dir), database)
            config = relay._read_config()
            baseline = time.time()
            config.update(
                {
                    "ignore_before": baseline,
                    "stable_minutes": 1,
                    "minimum_duration_minutes": 30,
                }
            )
            relay._write_config(config)

            old_file = anchor_dir / "测试主播_old.ts"
            old_file.write_bytes(b"old")
            old_time = baseline - 60
            old_file.touch()
            import os
            os.utime(old_file, (old_time, old_time))

            new_file = anchor_dir / "测试主播_new.ts"
            new_file.write_bytes(b"new recording")
            new_time = baseline + 1
            os.utime(new_file, (new_time, new_time))

            with patch.object(relay, "_probe_duration", return_value=3600):
                first = relay.scan_once(now=baseline + 2)
                second = relay.scan_once(now=baseline + 63)
            self.assertEqual(first["queued"], 0)
            self.assertEqual(first["detected"], 1)
            self.assertEqual(first["waiting_stable"], 1)
            self.assertEqual(second["queued"], 1)
            jobs = database.list_integration_jobs(JOB_KIND)
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["payload"]["file_name"], new_file.name)

    def test_unmatched_recording_is_reported_in_scan_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recording_dir = root / "recordings"
            recording_dir.mkdir(parents=True)
            database = Database(root / "workspace" / "test.db")
            relay = RecordingRelay(self.make_settings(root, recording_dir), database)
            config = relay._read_config()
            baseline = time.time()
            config["ignore_before"] = baseline
            relay._write_config(config)
            video = recording_dir / "未加入自动拆解的主播.ts"
            video.write_bytes(b"video")
            import os
            os.utime(video, (baseline + 1, baseline + 1))

            result = relay.scan_once(now=baseline + 2)

            self.assertEqual(result["detected"], 1)
            self.assertEqual(result["matched"], 0)
            self.assertEqual(result["unmatched"], 1)
            self.assertEqual(result["unmatched_files"], [video.name])


if __name__ == "__main__":
    unittest.main()
