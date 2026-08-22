from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


JSON_FIELDS = {
    "subcategories",
    "include_keywords",
    "exclude_keywords",
    "account_types",
    "preferred_traits",
    "reasons",
    "raw_data",
    "warnings",
    "payload",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS themes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    platform_category TEXT NOT NULL,
                    subcategories TEXT NOT NULL DEFAULT '[]',
                    include_keywords TEXT NOT NULL DEFAULT '[]',
                    exclude_keywords TEXT NOT NULL DEFAULT '[]',
                    min_price REAL,
                    max_price REAL,
                    max_followers INTEGER,
                    account_types TEXT NOT NULL DEFAULT '[]',
                    preferred_traits TEXT NOT NULL DEFAULT '[]',
                    target_audience TEXT NOT NULL DEFAULT '',
                    daily_limit INTEGER NOT NULL DEFAULT 5,
                    trial_recordings INTEGER NOT NULL DEFAULT 2,
                    auto_add INTEGER NOT NULL DEFAULT 0,
                    parser TEXT NOT NULL DEFAULT 'rules',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    theme_id INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
                    file_name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    imported_count INTEGER NOT NULL,
                    warnings TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    theme_id INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
                    import_id INTEGER REFERENCES imports(id) ON DELETE SET NULL,
                    source TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    anchor_name TEXT NOT NULL,
                    douyin_id TEXT NOT NULL DEFAULT '',
                    profile_url TEXT NOT NULL DEFAULT '',
                    analysis_url TEXT NOT NULL DEFAULT '',
                    auto_breakdown INTEGER NOT NULL DEFAULT 0,
                    followers REAL,
                    category TEXT NOT NULL DEFAULT '',
                    estimated_gmv REAL,
                    estimated_gmv_text TEXT NOT NULL DEFAULT '',
                    gmv_index REAL,
                    sales_volume REAL,
                    sales_volume_text TEXT NOT NULL DEFAULT '',
                    sales_index REAL,
                    gpm REAL,
                    uv_value REAL,
                    avg_online REAL,
                    duration_hours REAL,
                    sessions_7d REAL,
                    stability REAL,
                    account_type TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    products TEXT NOT NULL DEFAULT '',
                    score REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'candidate',
                    reasons TEXT NOT NULL DEFAULT '[]',
                    raw_data TEXT NOT NULL DEFAULT '{}',
                    imported_at TEXT NOT NULL,
                    UNIQUE(theme_id, source, source_key)
                );
                CREATE TABLE IF NOT EXISTS integration_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id INTEGER REFERENCES candidates(id) ON DELETE SET NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'queued',
                    payload TEXT NOT NULL DEFAULT '{}',
                    message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_candidates_theme_score ON candidates(theme_id, score DESC);
                CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
                """
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(candidates)").fetchall()}
            if "analysis_url" not in columns:
                db.execute("ALTER TABLE candidates ADD COLUMN analysis_url TEXT NOT NULL DEFAULT ''")
            if "auto_breakdown" not in columns:
                db.execute("ALTER TABLE candidates ADD COLUMN auto_breakdown INTEGER NOT NULL DEFAULT 0")
                db.execute("UPDATE candidates SET auto_breakdown=1 WHERE status='monitoring'")
            if "estimated_gmv_text" not in columns:
                db.execute("ALTER TABLE candidates ADD COLUMN estimated_gmv_text TEXT NOT NULL DEFAULT ''")
            if "gmv_index" not in columns:
                db.execute("ALTER TABLE candidates ADD COLUMN gmv_index REAL")
            if "sales_volume_text" not in columns:
                db.execute("ALTER TABLE candidates ADD COLUMN sales_volume_text TEXT NOT NULL DEFAULT ''")
            if "sales_index" not in columns:
                db.execute("ALTER TABLE candidates ADD COLUMN sales_index REAL")

            # 旧版网页榜单把灰色小字“指数”写进了 GMV/销量字段。该来源没有
            # 可验证的精确成交值，因此迁移为指数并清空伪装成实数的成交字段。
            db.execute(
                """
                UPDATE candidates
                SET gmv_index=estimated_gmv, estimated_gmv=NULL
                WHERE (
                    source LIKE '%网页榜单%'
                    OR EXISTS (
                        SELECT 1 FROM imports i
                        WHERE i.id=candidates.import_id AND i.file_name LIKE '%网页榜单%'
                    )
                )
                  AND estimated_gmv_text=''
                  AND gmv_index IS NULL
                  AND estimated_gmv IS NOT NULL
                """
            )
            db.execute(
                """
                UPDATE candidates
                SET sales_index=sales_volume, sales_volume=NULL
                WHERE (
                    source LIKE '%网页榜单%'
                    OR EXISTS (
                        SELECT 1 FROM imports i
                        WHERE i.id=candidates.import_id AND i.file_name LIKE '%网页榜单%'
                    )
                )
                  AND sales_volume_text=''
                  AND sales_index IS NULL
                  AND sales_volume IS NOT NULL
                """
            )

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        for key in JSON_FIELDS:
            if key in result and isinstance(result[key], str):
                try:
                    result[key] = json.loads(result[key])
                except json.JSONDecodeError:
                    pass
        if "auto_add" in result:
            result["auto_add"] = bool(result["auto_add"])
        if "active" in result:
            result["active"] = bool(result["active"])
        if "auto_breakdown" in result:
            result["auto_breakdown"] = bool(result["auto_breakdown"])
        return result

    def create_theme(self, data: dict[str, Any]) -> dict[str, Any]:
        timestamp = now_iso()
        fields = [
            "name", "description", "platform_category", "subcategories", "include_keywords",
            "exclude_keywords", "min_price", "max_price", "max_followers", "account_types",
            "preferred_traits", "target_audience", "daily_limit", "trial_recordings", "auto_add", "parser",
        ]
        values: list[Any] = []
        for field in fields:
            value = data.get(field)
            if field in JSON_FIELDS:
                value = json.dumps(value or [], ensure_ascii=False)
            if field == "auto_add":
                value = int(bool(value))
            if field == "daily_limit" and value is None:
                value = 5
            if field == "trial_recordings" and value is None:
                value = 2
            if field in {"description", "platform_category", "target_audience", "parser"} and value is None:
                value = ""
            values.append(value)
        with self.connect() as db:
            cursor = db.execute(
                f"INSERT INTO themes ({','.join(fields)},created_at,updated_at) VALUES ({','.join('?' for _ in fields)},?,?)",
                [*values, timestamp, timestamp],
            )
            theme_id = cursor.lastrowid
            row = db.execute("SELECT * FROM themes WHERE id = ?", (theme_id,)).fetchone()
        return self._decode(row) or {}

    def list_themes(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT t.*,
                    COUNT(c.id) AS candidate_count,
                    SUM(CASE WHEN c.status='approved' THEN 1 ELSE 0 END) AS approved_count,
                    SUM(CASE WHEN c.status='monitoring' THEN 1 ELSE 0 END) AS monitoring_count
                FROM themes t LEFT JOIN candidates c ON c.theme_id=t.id
                GROUP BY t.id ORDER BY t.created_at DESC
                """
            ).fetchall()
        return [self._decode(row) or {} for row in rows]

    def get_theme(self, theme_id: int) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM themes WHERE id = ?", (theme_id,)).fetchone()
        return self._decode(row)

    def delete_theme(self, theme_id: int) -> dict[str, int]:
        with self.connect() as db:
            theme = db.execute("SELECT id FROM themes WHERE id = ?", (theme_id,)).fetchone()
            if theme is None:
                raise ValueError("关注领域不存在或已被删除")
            candidate_count = int(
                db.execute(
                    "SELECT COUNT(*) FROM candidates WHERE theme_id = ?",
                    (theme_id,),
                ).fetchone()[0]
            )
            import_count = int(
                db.execute(
                    "SELECT COUNT(*) FROM imports WHERE theme_id = ?",
                    (theme_id,),
                ).fetchone()[0]
            )
            db.execute("DELETE FROM themes WHERE id = ?", (theme_id,))
        return {
            "theme_id": theme_id,
            "deleted_candidates": candidate_count,
            "deleted_imports": import_count,
        }

    def create_import(self, theme_id: int, file_name: str, source: str, row_count: int, imported_count: int, warnings: list[str]) -> int:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT INTO imports(theme_id,file_name,source,row_count,imported_count,warnings,created_at) VALUES (?,?,?,?,?,?,?)",
                (theme_id, file_name, source, row_count, imported_count, json.dumps(warnings, ensure_ascii=False), now_iso()),
            )
            return int(cursor.lastrowid)

    def upsert_candidates(self, theme_id: int, import_id: int, source: str, candidates: list[dict[str, Any]]) -> int:
        imported = 0
        with self.connect() as db:
            for candidate in candidates:
                db.execute(
                    """
                    INSERT INTO candidates(
                        theme_id,import_id,source,source_key,anchor_name,douyin_id,profile_url,analysis_url,followers,category,
                        estimated_gmv,estimated_gmv_text,gmv_index,sales_volume,sales_volume_text,sales_index,
                        gpm,uv_value,avg_online,duration_hours,sessions_7d,stability,
                        account_type,title,products,score,status,reasons,raw_data,imported_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(theme_id,source,source_key) DO UPDATE SET
                        import_id=excluded.import_id, anchor_name=excluded.anchor_name, douyin_id=excluded.douyin_id,
                        profile_url=excluded.profile_url, analysis_url=excluded.analysis_url,
                        followers=excluded.followers, category=excluded.category,
                        estimated_gmv=excluded.estimated_gmv, estimated_gmv_text=excluded.estimated_gmv_text,
                        gmv_index=excluded.gmv_index, sales_volume=excluded.sales_volume,
                        sales_volume_text=excluded.sales_volume_text, sales_index=excluded.sales_index, gpm=excluded.gpm,
                        uv_value=excluded.uv_value, avg_online=excluded.avg_online, duration_hours=excluded.duration_hours,
                        sessions_7d=excluded.sessions_7d, stability=excluded.stability, account_type=excluded.account_type,
                        title=excluded.title, products=excluded.products, score=excluded.score, reasons=excluded.reasons,
                        raw_data=excluded.raw_data, imported_at=excluded.imported_at
                    """,
                    (
                        theme_id, import_id, source, candidate["source_key"], candidate["anchor_name"],
                        candidate.get("douyin_id", ""), candidate.get("profile_url", ""),
                        candidate.get("analysis_url", ""), candidate.get("followers"),
                        candidate.get("category", ""), candidate.get("estimated_gmv"),
                        candidate.get("estimated_gmv_text", ""), candidate.get("gmv_index"),
                        candidate.get("sales_volume"), candidate.get("sales_volume_text", ""),
                        candidate.get("sales_index"),
                        candidate.get("gpm"), candidate.get("uv_value"), candidate.get("avg_online"),
                        candidate.get("duration_hours"), candidate.get("sessions_7d"), candidate.get("stability"),
                        candidate.get("account_type", ""), candidate.get("title", ""), candidate.get("products", ""),
                        candidate.get("score", 0), candidate.get("status", "candidate"),
                        json.dumps(candidate.get("reasons", []), ensure_ascii=False),
                        json.dumps(candidate.get("raw_data", {}), ensure_ascii=False), now_iso(),
                    ),
                )
                imported += 1
        return imported

    def list_candidates(self, theme_id: int | None = None, status: str = "", limit: int = 500) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if theme_id is not None:
            where.append("c.theme_id = ?")
            params.append(theme_id)
        if status:
            where.append("c.status = ?")
            params.append(status)
        sql_where = " WHERE " + " AND ".join(where) if where else ""
        with self.connect() as db:
            rows = db.execute(
                "SELECT c.*, t.name AS theme_name FROM candidates c JOIN themes t ON t.id=c.theme_id"
                + sql_where
                + " ORDER BY c.score DESC, c.imported_at DESC LIMIT ?",
                [*params, limit],
            ).fetchall()
        return [self._decode(row) or {} for row in rows]

    def update_candidate_status(self, candidate_ids: list[int], status: str) -> int:
        allowed = {"candidate", "approved", "monitoring", "rejected", "recorded", "analyzed"}
        if status not in allowed:
            raise ValueError("不支持的候选状态")
        if not candidate_ids:
            return 0
        placeholders = ",".join("?" for _ in candidate_ids)
        with self.connect() as db:
            cursor = db.execute(
                f"UPDATE candidates SET status=? WHERE id IN ({placeholders})",
                [status, *candidate_ids],
            )
            return cursor.rowcount

    def update_candidate_profile_urls(self, profile_urls: dict[int, str]) -> int:
        if not profile_urls:
            return 0
        with self.connect() as db:
            updated = 0
            for candidate_id, profile_url in profile_urls.items():
                cursor = db.execute(
                    "UPDATE candidates SET profile_url=? WHERE id=?",
                    (profile_url, candidate_id),
                )
                updated += cursor.rowcount
            return updated

    def set_candidate_auto_breakdown(self, candidate_ids: list[int], enabled: bool) -> int:
        if not candidate_ids:
            return 0
        placeholders = ",".join("?" for _ in candidate_ids)
        with self.connect() as db:
            cursor = db.execute(
                f"UPDATE candidates SET auto_breakdown=? WHERE id IN ({placeholders})",
                [int(enabled), *candidate_ids],
            )
            return cursor.rowcount

    def list_auto_breakdown_candidates(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT c.*, t.name AS theme_name
                FROM candidates c JOIN themes t ON t.id=c.theme_id
                WHERE c.auto_breakdown=1
                ORDER BY c.id
                """
            ).fetchall()
        return [self._decode(row) or {} for row in rows]

    def create_integration_job(
        self,
        candidate_id: int | None,
        kind: str,
        status: str,
        payload: dict[str, Any],
        message: str = "",
    ) -> int:
        timestamp = now_iso()
        with self.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO integration_jobs(
                    candidate_id,kind,status,payload,message,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    candidate_id,
                    kind,
                    status,
                    json.dumps(payload, ensure_ascii=False),
                    message,
                    timestamp,
                    timestamp,
                ),
            )
            return int(cursor.lastrowid)

    def find_integration_job(self, kind: str, source_path: str) -> dict[str, Any] | None:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM integration_jobs WHERE kind=? ORDER BY id DESC",
                (kind,),
            ).fetchall()
        for row in rows:
            decoded = self._decode(row) or {}
            if str((decoded.get("payload") or {}).get("source_path") or "") == source_path:
                return decoded
        return None

    def update_integration_job(
        self,
        job_id: int,
        status: str,
        message: str = "",
        payload_updates: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM integration_jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise ValueError("接力任务不存在")
            payload = json.loads(row["payload"] or "{}")
            payload.update(payload_updates or {})
            db.execute(
                """
                UPDATE integration_jobs
                SET status=?,message=?,payload=?,updated_at=?
                WHERE id=?
                """,
                (
                    status,
                    message,
                    json.dumps(payload, ensure_ascii=False),
                    now_iso(),
                    job_id,
                ),
            )

    def list_integration_jobs(self, kind: str = "", limit: int = 50) -> list[dict[str, Any]]:
        where = "WHERE j.kind=?" if kind else ""
        params: list[Any] = [kind] if kind else []
        with self.connect() as db:
            rows = db.execute(
                f"""
                SELECT j.*, c.anchor_name
                FROM integration_jobs j
                LEFT JOIN candidates c ON c.id=j.candidate_id
                {where}
                ORDER BY j.id DESC LIMIT ?
                """,
                [*params, limit],
            ).fetchall()
        return [self._decode(row) or {} for row in rows]

    def get_integration_job(self, job_id: int) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                """
                SELECT j.*, c.anchor_name
                FROM integration_jobs j
                LEFT JOIN candidates c ON c.id=j.candidate_id
                WHERE j.id=?
                """,
                (job_id,),
            ).fetchone()
        return self._decode(row)

    def requeue_interrupted_integration_jobs(self, kind: str) -> list[int]:
        in_progress = {
            "starting",
            "checking",
            "extracting_audio",
            "uploading",
            "transcribing",
            "analyzing",
            "exporting",
        }
        placeholders = ",".join("?" for _ in in_progress)
        with self.connect() as db:
            rows = db.execute(
                f"""
                SELECT id FROM integration_jobs
                WHERE kind=? AND status IN ({placeholders})
                """,
                [kind, *sorted(in_progress)],
            ).fetchall()
            ids = [int(row["id"]) for row in rows]
            if ids:
                id_placeholders = ",".join("?" for _ in ids)
                db.execute(
                    f"""
                    UPDATE integration_jobs
                    SET status='queued',message='Agent重启，任务已重新排队',updated_at=?
                    WHERE id IN ({id_placeholders})
                    """,
                    [now_iso(), *ids],
                )
        return ids

    def dashboard(self) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM themes WHERE active=1) AS themes,
                    (SELECT COUNT(*) FROM candidates) AS candidates,
                    (SELECT COUNT(*) FROM candidates WHERE status='approved') AS approved,
                    (SELECT COUNT(*) FROM candidates WHERE status='monitoring') AS monitoring,
                    (SELECT COUNT(*) FROM imports) AS imports
                """
            ).fetchone()
        return dict(row) if row else {}
