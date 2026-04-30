"""
MOM - Response Cache
====================
Stores search analysis, source type, and response data in the database.
If the same request arrives again within the TTL interval, serves from DB.
If no valid record exists, signals caller to perform a fresh search and then
stores the new result.

Table: search_response_cache
─────────────────────────────────────────────────────────────────────────────
cache_key        TEXT PRIMARY KEY   – normalised hash of (concept + source_type)
concept          TEXT               – original search concept / query
source_type      TEXT               – e.g. "web", "wikipedia", "internal", "ai"
search_analysis  TEXT (JSON)        – meta about the search (keywords, filters …)
response_data    TEXT (JSON)        – the actual response payload
created_at       REAL               – Unix timestamp of first storage
last_served_at   REAL               – Unix timestamp of last cache hit
serve_count      INTEGER            – how many times this entry was served from cache
ttl_seconds      REAL               – time-to-live; configurable per source_type
is_valid         INTEGER            – 1 = active, 0 = invalidated manually
"""

import sqlite3
import hashlib
import json
import time
import logging
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

# ── Default TTL per source type (seconds) ────────────────────────────────────
DEFAULT_TTL: dict[str, float] = {
    "web":        60 * 60 * 6,    # 6 hours  – web results change moderately
    "wikipedia":  60 * 60 * 24,   # 24 hours – encyclopedia, stable
    "internal":   60 * 60 * 12,   # 12 hours – internal KB
    "ai":         60 * 60 * 1,    # 1 hour   – AI responses may vary
    "default":    60 * 60 * 3,    # 3 hours  – fallback
}


class ResponseCache:
    """
    Thin SQLite-backed cache layer for search responses.

    Usage
    -----
    cache = ResponseCache("storage/knowledge.db")

    # Before doing a live search:
    hit = cache.get("Zero", source_type="web")
    if hit:
        return hit["response_data"]          # serve from cache

    # After getting a fresh result:
    cache.set(
        concept="Zero",
        source_type="web",
        search_analysis={"keywords": ["zero", "number"]},
        response_data={"summary": "...", "sources": [...]},
    )
    """

    def __init__(self, db_path: str = "storage/knowledge.db",
                 custom_ttl: Optional[dict[str, float]] = None):
        self.db_path = db_path
        self.ttl_map = {**DEFAULT_TTL, **(custom_ttl or {})}
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_response_cache (
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
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_concept
                ON search_response_cache (concept)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_valid_expires
                ON search_response_cache (is_valid, created_at, ttl_seconds)
            """)
            conn.commit()
        logger.debug("ResponseCache: DB initialised at %s", self.db_path)

    @staticmethod
    def _make_key(concept: str, source_type: str) -> str:
        raw = f"{concept.strip().lower()}::{source_type.strip().lower()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _is_fresh(self, row: sqlite3.Row) -> bool:
        age = time.time() - row["created_at"]
        return bool(row["is_valid"]) and age < row["ttl_seconds"]

    def _ttl_for(self, source_type: str) -> float:
        return self.ttl_map.get(source_type, self.ttl_map["default"])

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, concept: str,
            source_type: str = "default") -> Optional[dict]:
        """
        Returns cached record dict if a fresh entry exists, else None.

        Returned dict keys:
            concept, source_type, search_analysis, response_data,
            created_at, serve_count, cache_age_seconds
        """
        key = self._make_key(concept, source_type)
        now = time.time()

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM search_response_cache WHERE cache_key = ?",
                (key,)
            ).fetchone()

            if row is None:
                logger.debug("Cache MISS (not found): %s / %s", concept, source_type)
                return None

            if not self._is_fresh(row):
                logger.debug("Cache MISS (stale/invalid): %s / %s", concept, source_type)
                return None

            # Update serve stats
            conn.execute("""
                UPDATE search_response_cache
                SET last_served_at = ?, serve_count = serve_count + 1
                WHERE cache_key = ?
            """, (now, key))
            conn.commit()

        logger.info("Cache HIT: %s / %s  (served %d times)",
                    concept, source_type, row["serve_count"] + 1)
        return {
            "concept":          row["concept"],
            "source_type":      row["source_type"],
            "search_analysis":  json.loads(row["search_analysis"]),
            "response_data":    json.loads(row["response_data"]),
            "created_at":       row["created_at"],
            "serve_count":      row["serve_count"] + 1,
            "cache_age_seconds": now - row["created_at"],
        }

    def set(self, concept: str,
            source_type: str = "default",
            search_analysis: Any = None,
            response_data: Any = None,
            ttl_seconds: Optional[float] = None) -> str:
        """
        Insert or replace a cache record.
        Returns the cache_key for reference.
        """
        key      = self._make_key(concept, source_type)
        now      = time.time()
        ttl      = ttl_seconds or self._ttl_for(source_type)
        analysis = json.dumps(search_analysis or {})
        payload  = json.dumps(response_data  or {})

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO search_response_cache
                    (cache_key, concept, source_type, search_analysis,
                     response_data, created_at, last_served_at,
                     serve_count, ttl_seconds, is_valid)
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

        logger.info("Cache SET: %s / %s  (TTL %.0fs)", concept, source_type, ttl)
        return key

    def invalidate(self, concept: str,
                   source_type: Optional[str] = None) -> int:
        """
        Manually invalidate cache entries for a concept.
        If source_type is None, invalidates all source types for that concept.
        Returns count of rows affected.
        """
        with self._connect() as conn:
            if source_type:
                key = self._make_key(concept, source_type)
                cur = conn.execute("""
                    UPDATE search_response_cache SET is_valid = 0
                    WHERE cache_key = ?
                """, (key,))
            else:
                cur = conn.execute("""
                    UPDATE search_response_cache SET is_valid = 0
                    WHERE lower(concept) = lower(?)
                """, (concept,))
            conn.commit()
            count = cur.rowcount

        logger.info("Cache INVALIDATED: %s / %s  (%d rows)",
                    concept, source_type or "ALL", count)
        return count

    def purge_expired(self) -> int:
        """Delete all expired or invalid rows. Called by MaintenanceEngine."""
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute("""
                DELETE FROM search_response_cache
                WHERE is_valid = 0
                   OR (? - created_at) >= ttl_seconds
            """, (now,))
            conn.commit()
            count = cur.rowcount
        logger.info("Cache PURGE: removed %d stale/invalid entries", count)
        return count

    def stats(self) -> dict:
        """Return a quick summary of cache health."""
        now = time.time()
        with self._connect() as conn:
            total   = conn.execute("SELECT COUNT(*) FROM search_response_cache").fetchone()[0]
            fresh   = conn.execute("""
                SELECT COUNT(*) FROM search_response_cache
                WHERE is_valid = 1 AND (? - created_at) < ttl_seconds
            """, (now,)).fetchone()[0]
            hits    = conn.execute("""
                SELECT COALESCE(SUM(serve_count), 0) FROM search_response_cache
            """).fetchone()[0]
            by_src  = conn.execute("""
                SELECT source_type, COUNT(*) as cnt
                FROM search_response_cache
                WHERE is_valid = 1
                GROUP BY source_type
            """).fetchall()

        return {
            "total_entries":  total,
            "fresh_entries":  fresh,
            "stale_entries":  total - fresh,
            "total_hits":     hits,
            "by_source_type": {r["source_type"]: r["cnt"] for r in by_src},
        }
