from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from live_breakdown_agent.aliyun import DashScopeAsrClient, parse_asr_result
from live_breakdown_agent.analyzer import chunk_segments, coarsen_event_rows, rebalance_event_rows, renumber_products_by_first_event, split_long_event_rows
from live_breakdown_agent.models import EventRow, TranscriptSegment, format_hms, validate_event_rows, validate_transcript
from live_breakdown_agent.state import JobState, JobStore


class CoreTests(unittest.TestCase):
    def test_second_timestamp(self) -> None:
        self.assertEqual(format_hms(3661.49), "01:01:01")
        self.assertEqual(EventRow(1, 65, "互动", "大家好").timestamp, "00:00:01-00:01:05")
        self.assertEqual(EventRow(24.1, 24.4, "库存", "七个").timestamp, "00:00:24-00:00:25")

    def test_transcript_order_guard(self) -> None:
        validate_transcript([TranscriptSegment(0, 2, "一"), TranscriptSegment(2, 4, "二")])
        with self.assertRaises(ValueError):
            validate_transcript([TranscriptSegment(10, 12, "一"), TranscriptSegment(1, 2, "二")])

    def test_asr_parser_millisecond_timestamps(self) -> None:
        result = {"transcripts": [{"sentences": [{"begin_time": 12000, "end_time": 15000, "text": "测试"}]}]}
        rows = parse_asr_result(result)
        self.assertEqual((rows[0].start, rows[0].end), (12.0, 15.0))

    def test_asr_parser_preserves_zero_duration_text(self) -> None:
        result = {"transcripts": [{"sentences": [{"begin_time": 1000, "end_time": 1000, "text": "嗯"}]}]}
        rows = parse_asr_result(result)
        self.assertEqual(rows[0].text, "嗯")
        self.assertGreater(rows[0].end, rows[0].start)

    def test_long_second_timestamps_are_not_treated_as_milliseconds(self) -> None:
        result = {"sentences": [{"start": 10800, "end": 10805, "text": "三小时以后"}]}
        rows = parse_asr_result(result)
        self.assertEqual((rows[0].start, rows[0].end), (10800.0, 10805.0))

    def test_qwen_filetrans_uses_single_file_url(self) -> None:
        client = DashScopeAsrClient("key", "https://example.test", "qwen3-asr-flash-filetrans")
        with patch("live_breakdown_agent.aliyun.request_json", return_value={"output": {"task_id": "task-1"}}) as mocked:
            self.assertEqual(client.submit("https://example.test/audio.flac"), "task-1")
        body = mocked.call_args.args[3]
        self.assertEqual(body["input"], {"file_url": "https://example.test/audio.flac"})

    def test_chunking_happens_on_complete_transcript_structure(self) -> None:
        segments = [TranscriptSegment(i * 10, i * 10 + 9, "甲" * 10) for i in range(5)]
        chunks = chunk_segments(segments, max_chars=25, max_seconds=999)
        self.assertEqual([len(chunk) for chunk in chunks], [2, 2, 1])

    def test_event_validation(self) -> None:
        validate_event_rows([EventRow(0, 3, "做人设", "我以前也这样")])

    def test_event_rows_are_merged_to_one_to_five_minutes(self) -> None:
        rows = [EventRow(i * 20, (i + 1) * 20, f"第1品-镜框｜动作{i}", f"原文{i}") for i in range(7)]
        merged = coarsen_event_rows(rows)
        self.assertEqual([(row.start, row.end) for row in merged], [(0, 60), (60, 140)])
        self.assertIn("动作0+动作1+动作2", merged[0].event)

    def test_coarse_rows_do_not_display_overlapping_boundaries(self) -> None:
        rows = [EventRow(0, 66.4, "第1品｜讲解", "甲"), EventRow(66.1, 130, "第1品｜催单", "乙")]
        merged = coarsen_event_rows(rows)
        self.assertEqual([row.timestamp for row in merged], ["00:00:00-00:01:07", "00:01:07-00:02:10"])

    def test_subsecond_alignment_keeps_displayed_one_minute_event(self) -> None:
        rows = [
            EventRow(0, 60.4, "第1品｜讲解", "甲"),
            EventRow(60.1, 120.2, "第1品｜催单", "乙"),
        ]
        merged = coarsen_event_rows(rows)
        self.assertEqual(
            [row.timestamp for row in merged],
            ["00:00:00-00:01:01", "00:01:01-00:02:01"],
        )

    def test_display_rounding_does_not_create_one_second_overlap(self) -> None:
        rows = [EventRow(0, 299.2, "第1品｜讲解", "甲"), EventRow(299.7, 370, "第1品｜催单", "乙")]
        merged = coarsen_event_rows(rows)
        self.assertEqual([row.timestamp for row in merged], ["00:00:00-00:05:00", "00:05:00-00:06:10"])

    def test_long_model_event_is_split_on_source_sentences(self) -> None:
        segments = [TranscriptSegment(i * 30, (i + 1) * 30, str(i)) for i in range(13)]
        rows = split_long_event_rows([EventRow(0, 390, "第1品｜讲解", "原文")], segments)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row.end - row.start <= 300 for row in rows))

    def test_short_trailing_event_is_rebalanced_without_loss(self) -> None:
        segments = [TranscriptSegment(i * 30, min(321, (i + 1) * 30), str(i)) for i in range(11)]
        rows = [
            EventRow(0, 280, "第1品｜讲解", "前段"),
            EventRow(280, 321, "第1品｜结束", "尾段"),
        ]
        coarse = coarsen_event_rows(rows, allow_oversized_tail=True, allow_short=True)
        self.assertEqual(len(coarse), 1)
        final = rebalance_event_rows(coarse, segments)
        self.assertTrue(all(60 <= row.end - row.start <= 300 for row in final))
        self.assertEqual(final[0].start, 0)
        self.assertEqual(final[-1].end, 321)

    def test_products_are_renumbered_by_first_timeline_appearance(self) -> None:
        rows = [
            EventRow(0, 60, "第1品-银瓶｜讲解", "一"),
            EventRow(60, 120, "第3品-双仓饮｜卖点；第1品-银瓶｜催单", "二"),
            EventRow(120, 180, "第6品-囤货装｜价格", "三"),
        ]
        products = [{"number": 1, "name": "银瓶"}, {"number": 3, "name": "双仓饮"}, {"number": 6, "name": "囤货装"}]
        new_rows, new_products = renumber_products_by_first_event(rows, products)
        self.assertEqual([row.event.split("｜", 1)[0] for row in new_rows], ["第1品-银瓶", "第2品-双仓饮", "第3品-囤货装"])
        self.assertEqual([product["number"] for product in new_products], [1, 2, 3])

    def test_state_cannot_go_backwards(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = JobStore(Path(temp))
            state = JobState(job_id="x", source_video="x.mp4")
            store.save(state)
            store.advance(state, "transcription_validated")
            with self.assertRaises(ValueError):
                store.advance(state, "audio_extracted")
            self.assertEqual(json.loads(store.path.read_text(encoding="utf-8"))["stage"], "transcription_validated")


if __name__ == "__main__":
    unittest.main()
