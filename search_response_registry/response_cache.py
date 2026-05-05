import sqlite3
import hashlib
import json
import time
import logging
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

DEFAULT_TTL: dict[str, float] = {
    "web":              60 * 60 * 6,
    "wikipedia":        60 * 60 * 24,
    "arxiv":            60 * 60 * 12,
    "semantic_scholar": 60 * 60 * 12,
    "ai":               60 * 60 * 1,
    "default":          60 * 60 * 3,
}


class ResponseCache:

    def __init__(self, db_path: str = "storage/knowledge.db",
                 custom_ttl: Optional[dict[str, float]] = None):
        self.db_path = db_path
        self.ttl_map = {**DEFAULT_TTL, **(custom_ttl or {})}
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_response_registry (
                    cache_key        TEXT PRIMARY KEY,
                    concept          TEXT    NOT NULL,
                    source_type      TEXT    NOT NULL DEFAULT 'default',
                    search_analysis  TEXT    NOT NULL DEFAULT '{}',
                    response_data    TEXT    NOT NULL DEFAULT '{}',
                    created_at       REAL    NOT NULL,
                    last_served_at   REAL,
                    serve_count      INTEGER NOT NULL DEFAULT 0,
                    ttl_seconds      REAL    NOT NULL,
                    is_valid         INTEGER NOT NULL DEFAULT 1
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_registry_concept ON search_response_registry (concept)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_registry_valid_expires ON search_response_registry (is_valid, created_at, ttl_seconds)")
            conn.commit()

    @staticmethod
    def _make_key(concept: str, source_type: str) -> str:
        raw = f"{concept.strip().lower()}::{source_type.strip().lower()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _is_fresh(self, row: sqlite3.Row) -> bool:
        age = time.time() - row["created_at"]
        return bool(row["is_valid"]) and age < row["ttl_seconds"]

    def _ttl_for(self, source_type: str) -> float:
        return self.ttl_map.get(source_type, self.ttl_map["default"])

    def get(self, concept: str, source_type: str = "default") -> Optional[dict]:
        key = self._make_key(concept, source_type)
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM search_response_registry WHERE cache_key = ?", (key,)
            ).fetchone()
            if row is None or not self._is_fresh(row):
                return None
            conn.execute("""
                UPDATE search_response_registry
                SET last_served_at = ?, serve_count = serve_count + 1
                WHERE cache_key = ?
            """, (now, key))
            conn.commit()
        return {
            "concept":           row["concept"],
            "source_type":       row["source_type"],
            "search_analysis":   json.loads(row["search_analysis"]),
            "response_data":     json.loads(row["response_data"]),
            "created_at":        row["created_at"],
            "serve_count":       row["serve_count"] + 1,
            "cache_age_seconds": now - row["created_at"],
        }

    def set(self, concept: str, source_type: str = "default",
            search_analysis: Any = None, response_data: Any = None,
            ttl_seconds: Optional[float] = None) -> str:
        key      = self._make_key(concept, source_type)
        now      = time.time()
        ttl      = ttl_seconds or self._ttl_for(source_type)
        analysis = json.dumps(search_analysis or {})
        payload  = json.dumps(response_data or {})
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO search_response_registry
                    (cache_key, concept, source_type, search_analysis,
                     response_data, created_at, last_served_at, serve_count, ttl_seconds, is_valid)
                VALUES (?, ?, ?, ?, ?, ?, NULL, 0, ?, 1)
                ON CONFLICT(cache_key) DO UPDATE SET
                    search_analysis = excluded.search_analysis,
                    response_data   = excluded.response_data,
                    created_at      = excluded.created_at,
                    ttl_seconds     = excluded.ttl_seconds,
                    serve_count     = 0,
                    is_valid        = 1
            """, (key, concept, source_type, analysis, payload, now, ttl))
            conn.commit()
        return key

    def invalidate(self, concept: str, source_type: Optional[str] = None) -> int:
        with self._connect() as conn:
            if source_type:
                key = self._make_key(concept, source_type)
                cur = conn.execute("UPDATE search_response_registry SET is_valid = 0 WHERE cache_key = ?", (key,))
            else:
                cur = conn.execute("UPDATE search_response_registry SET is_valid = 0 WHERE lower(concept) = lower(?)", (concept,))
            conn.commit()
        return cur.rowcount

    def purge_expired(self) -> int:
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute("""
                DELETE FROM search_response_registry
                WHERE is_valid = 0 OR (? - created_at) >= ttl_seconds
            """, (now,))
            conn.commit()
        return cur.rowcount

    def stats(self) -> dict:
        now = time.time()
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM search_response_registry").fetchone()[0]
            fresh = conn.execute("SELECT COUNT(*) FROM search_response_registry WHERE is_valid = 1 AND (? - created_at) < ttl_seconds", (now,)).fetchone()[0]
            hits  = conn.execute("SELECT COALESCE(SUM(serve_count), 0) FROM search_response_registry").fetchone()[0]
            by_src = conn.execute("SELECT source_type, COUNT(*) as cnt FROM search_response_registry WHERE is_valid = 1 GROUP BY source_type").fetchall()
        return {
            "total_entries":  total,
            "fresh_entries":  fresh,
            "stale_entries":  total - fresh,
            "total_hits":     hits,
            "by_source_type": {r["source_type"]: r["cnt"] for r in by_src},
        }