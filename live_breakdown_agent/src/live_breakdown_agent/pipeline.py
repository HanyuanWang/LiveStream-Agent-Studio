from __future__ import annotations

import json
import uuid
from pathlib import Path

from .aliyun import DashScopeAsrClient, OssUploader, parse_asr_result
from .analyzer import QwenAnalyzer, renumber_products_by_first_event
from .config import Settings
from .excel import export_excel
from .media import extract_audio, inspect_media
from .models import TranscriptSegment, validate_transcript
from .state import STAGES, JobState, JobStore


class LiveBreakdownAgent:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run(self, video_path: Path, audio_url: str = "") -> Path:
        video_path = video_path.resolve()
        if not video_path.exists():
            raise FileNotFoundError(video_path)
        self._require_runtime()
        job_id = f"{video_path.stem[:40]}-{uuid.uuid4().hex[:8]}"
        job_dir = self.settings.workspace_dir / "jobs" / job_id
        store = JobStore(job_dir)
        state = JobState(job_id=job_id, source_video=str(video_path))
        store.save(state)

        self._progress("1/8 检查视频")
        media_info = inspect_media(video_path, self.settings.ffprobe_path)  # type: ignore[arg-type]
        (job_dir / "media.json").write_text(json.dumps(media_info, ensure_ascii=False, indent=2), encoding="utf-8")
        store.advance(state, "media_inspected")

        self._progress("2/8 提取音频")
        audio_path = extract_audio(video_path, job_dir / "audio.flac", self.settings.ffmpeg_path)  # type: ignore[arg-type]
        store.advance(state, "audio_extracted")

        return self._continue_from_audio(video_path, audio_path, job_dir, store, state, audio_url)

    def resume_job(self, job_dir: Path) -> Path:
        """从完整转写、原始 ASR 结果或已提取音频继续。"""
        self._require_runtime()
        job_dir = job_dir.resolve()
        store = JobStore(job_dir)
        state = store.load()
        video_path = Path(state.source_video)
        self._progress(f"从断点继续：{job_dir.name}")
        transcript_path = job_dir / "transcript.json"
        if transcript_path.exists():
            data = json.loads(transcript_path.read_text(encoding="utf-8"))
            segments = [TranscriptSegment(float(x["start"]), float(x["end"]), str(x["text"])) for x in data]
            validate_transcript(segments)
            if STAGES.index(state.stage) < STAGES.index("transcription_validated"):
                store.advance(state, "transcription_validated")
            return self._analyze_and_export(video_path, job_dir, store, state, segments, {})

        raw_path = job_dir / "asr_raw.json"
        if raw_path.exists():
            self._progress("从已下载的完整 ASR 结果继续，不重复转写")
            raw_asr = json.loads(raw_path.read_text(encoding="utf-8"))
            segments = parse_asr_result(raw_asr)
            transcript_path.write_text(json.dumps([s.to_dict() for s in segments], ensure_ascii=False, indent=2), encoding="utf-8")
            store.advance(state, "transcription_complete")
            validate_transcript(segments)
            store.advance(state, "transcription_validated")
            task_result: dict = {}
            if state.task_id:
                asr = DashScopeAsrClient(self.settings.dashscope_api_key, self.settings.dashscope_base_url, self.settings.asr_model)
                task_result = asr.poll(state.task_id)
            return self._analyze_and_export(video_path, job_dir, store, state, segments, task_result.get("usage", {}))

        if state.stage == "transcription_submitted" and state.task_id:
            self._progress("检测到已提交的转写任务，继续等待现有任务，不重新上传或计费")
            asr = DashScopeAsrClient(
                self.settings.dashscope_api_key,
                self.settings.dashscope_base_url,
                self.settings.asr_model,
            )
            task_result = asr.poll(state.task_id)
            raw_asr = asr.download_result(task_result)
            raw_path.write_text(json.dumps(raw_asr, ensure_ascii=False, indent=2), encoding="utf-8")

            if state.audio_url:
                self._require_oss()
                uploader = OssUploader(
                    self.settings.oss_endpoint,
                    self.settings.oss_bucket,
                    self.settings.oss_access_key_id,
                    self.settings.oss_access_key_secret,
                    self.settings.oss_security_token,
                )
                uploader.delete(f"live-breakdown/{state.job_id}/audio.flac")
                state.audio_url = ""
                store.save(state)

            segments = parse_asr_result(raw_asr)
            transcript_path.write_text(
                json.dumps([s.to_dict() for s in segments], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            store.advance(state, "transcription_complete")
            validate_transcript(segments)
            store.advance(state, "transcription_validated")
            return self._analyze_and_export(
                video_path,
                job_dir,
                store,
                state,
                segments,
                task_result.get("usage", {}),
            )

        audio_path = job_dir / "audio.flac"
        if not audio_path.exists():
            raise FileNotFoundError(f"任务没有可续跑的 transcript.json、asr_raw.json 或 audio.flac: {job_dir}")
        if state.stage != "audio_extracted":
            raise RuntimeError(f"无法从阶段 {state.stage} 续跑，缺少完整转写文件")
        return self._continue_from_audio(video_path, audio_path, job_dir, store, state, "")

    def _continue_from_audio(self, video_path: Path, audio_path: Path, job_dir: Path, store: JobStore, state: JobState, audio_url: str) -> Path:

        uploaded_object_key = ""
        uploader = None
        if not audio_url:
            self._progress("3/8 上传私有 OSS 临时音频")
            self._require_oss()
            uploader = OssUploader(
                self.settings.oss_endpoint, self.settings.oss_bucket,
                self.settings.oss_access_key_id, self.settings.oss_access_key_secret,
                self.settings.oss_security_token,
            )
            uploaded_object_key = f"live-breakdown/{state.job_id}/audio.flac"
            audio_url = uploader.upload_and_sign(audio_path, uploaded_object_key)
        store.advance(state, "audio_uploaded", audio_url=audio_url)

        asr = DashScopeAsrClient(self.settings.dashscope_api_key, self.settings.dashscope_base_url, self.settings.asr_model)
        self._progress("4/8 提交整场转写并等待完成（此阶段不会分析事件）")
        task_id = asr.submit(audio_url)
        store.advance(state, "transcription_submitted", task_id=task_id)
        task_result = asr.poll(task_id)
        raw_asr = asr.download_result(task_result)
        (job_dir / "asr_raw.json").write_text(json.dumps(raw_asr, ensure_ascii=False, indent=2), encoding="utf-8")
        if uploader and uploaded_object_key:
            uploader.delete(uploaded_object_key)
            state.audio_url = ""
            store.save(state)
        segments = parse_asr_result(raw_asr)
        (job_dir / "transcript.json").write_text(json.dumps([s.to_dict() for s in segments], ensure_ascii=False, indent=2), encoding="utf-8")
        store.advance(state, "transcription_complete")

        # 硬性闸门：完整转写通过验证之前，不允许启动事件分析。
        validate_transcript(segments)
        store.advance(state, "transcription_validated")

        return self._analyze_and_export(video_path, job_dir, store, state, segments, task_result.get("usage", {}))

    def _analyze_and_export(self, video_path: Path, job_dir: Path, store: JobStore, state: JobState, segments: list[TranscriptSegment], asr_usage: dict) -> Path:

        self._progress("5/8 完整转写已校验，开始建立全场商品表")
        analyzer = QwenAnalyzer(self.settings.dashscope_api_key, self.settings.dashscope_base_url, self.settings.text_model, job_dir / "qwen_cache")
        products_path = job_dir / "products.json"
        if products_path.exists():
            products = json.loads(products_path.read_text(encoding="utf-8"))
        else:
            products = analyzer.build_product_registry(segments)
            products_path.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
        self._progress("6/8 按 1–5 分钟分析事件")
        rows = analyzer.analyze(segments, products)
        rows, products = renumber_products_by_first_event(rows, products)
        (job_dir / "analysis.json").write_text(json.dumps({"products": products, "rows": [r.to_dict() for r in rows]}, ensure_ascii=False, indent=2), encoding="utf-8")
        if STAGES.index(state.stage) < STAGES.index("analysis_complete"):
            store.advance(state, "analysis_complete")

        cached_usage: list[dict] = []
        cache_dir = job_dir / "qwen_cache"
        if cache_dir.exists():
            for cache_file in sorted(cache_dir.glob("*.json")):
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                if cached.get("usage"):
                    cached_usage.append(cached["usage"])
        text_usage = cached_usage or analyzer.usage_records
        usage = {
            "asr": asr_usage,
            "text_calls": text_usage,
            "text_total": {
                "input_tokens": sum(int(x.get("prompt_tokens", x.get("input_tokens", 0)) or 0) for x in text_usage),
                "output_tokens": sum(int(x.get("completion_tokens", x.get("output_tokens", 0)) or 0) for x in text_usage),
                "total_tokens": sum(int(x.get("total_tokens", 0) or 0) for x in text_usage),
            },
        }
        (job_dir / "usage.json").write_text(json.dumps(usage, ensure_ascii=False, indent=2), encoding="utf-8")

        self._progress("7/8 导出三列 Excel")
        output = self.settings.workspace_dir / "output" / f"{video_path.stem}_拆解.xlsx"
        export_excel(rows, output)
        if STAGES.index(state.stage) < STAGES.index("excel_exported"):
            store.advance(state, "excel_exported")
        self._progress(f"8/8 完成：{output}")
        return output

    @staticmethod
    def _progress(message: str) -> None:
        print(f"[直播拆解] {message}", flush=True)

    def analyze_transcript_file(self, transcript_path: Path, output_path: Path) -> Path:
        self._require_dashscope()
        data = json.loads(transcript_path.read_text(encoding="utf-8-sig"))
        segments = [TranscriptSegment(float(x["start"]), float(x["end"]), str(x["text"])) for x in data]
        validate_transcript(segments)
        analyzer = QwenAnalyzer(self.settings.dashscope_api_key, self.settings.dashscope_base_url, self.settings.text_model)
        products = analyzer.build_product_registry(segments)
        rows = analyzer.analyze(segments, products)
        self._require_excel()
        return export_excel(rows, output_path)

    def _require_dashscope(self) -> None:
        if not self.settings.dashscope_api_key:
            raise RuntimeError("缺少 DASHSCOPE_API_KEY，请在 .env 中填写")

    def _require_runtime(self) -> None:
        self._require_dashscope()
        if not self.settings.ffmpeg_path or not self.settings.ffprobe_path:
            raise RuntimeError("未找到 ffmpeg/ffprobe，请在 .env 配置路径")
        self._require_excel()

    def _require_excel(self) -> None:
        try:
            import openpyxl  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("未安装 openpyxl，无法导出 Excel") from exc

    def _require_oss(self) -> None:
        required = [self.settings.oss_endpoint, self.settings.oss_bucket, self.settings.oss_access_key_id, self.settings.oss_access_key_secret]
        if not all(required):
            raise RuntimeError("未提供 audio_url，且 OSS 配置不完整")
