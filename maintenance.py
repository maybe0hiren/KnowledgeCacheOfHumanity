"""
MOM - Maintenance Engine
========================
Plugs into your existing runMaintenance() hook.

Two responsibilities
--------------------
1. LRU DEMOTION  – uses lastAccessed timestamp to move concepts that haven't
   been touched for a long time:  hot → warm → cold

2. ARU RE-RANKING – after each search cycle, recomputes each concept's weight
   from (search_frequency, recency, rediscovery_count) and updates the
   storage_layer accordingly:
       weight ≥ HOT_THRESHOLD  → hot
       weight ≥ WARM_THRESHOLD → warm
       else                    → cold

Compatible with the existing `storage/` SQLite schema used by rankingManager.py.
Expects a `concepts` table with at least:

    id, concept_name, storage_layer, last_accessed (Unix ts),
    search_count, rediscovery_count, weight (REAL)

If any column is missing the engine will add it via ALTER TABLE.
"""

import sqlite3
import time
import math
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Thresholds (tune to taste) ────────────────────────────────────────────────
HOT_THRESHOLD  = 0.65   # weight ≥ this → hot
WARM_THRESHOLD = 0.30   # weight ≥ this → warm  (else cold)

# LRU age limits (seconds) before demotion regardless of weight
LRU_HOT_MAX_AGE  = 60 * 60 * 24 * 3    # 3 days  idle → demote hot  → warm
LRU_WARM_MAX_AGE = 60 * 60 * 24 * 14   # 14 days idle → demote warm → cold

# ARU weight formula parameters
FREQ_WEIGHT    = 0.45   # how much search_count matters
RECENCY_WEIGHT = 0.35   # how much last_accessed matters
REDISCO_WEIGHT = 0.20   # how much rediscovery_count matters
RECENCY_DECAY  = 0.0001 # controls how fast recency score decays with age (per second)


@dataclass
class MaintenanceReport:
    """Summary of one runMaintenance() call."""
    lru_demotions:   dict = field(default_factory=dict)  # {concept: old→new}
    aru_promotions:  dict = field(default_factory=dict)  # {concept: old→new}
    aru_demotions:   dict = field(default_factory=dict)
    weights_updated: int  = 0
    cache_purged:    int  = 0
    duration_ms:     float = 0.0

    def summary(self) -> str:
        return (
            f"Maintenance done in {self.duration_ms:.1f}ms | "
            f"LRU demotions: {len(self.lru_demotions)} | "
            f"ARU promotions: {len(self.aru_promotions)} | "
            f"ARU demotions: {len(self.aru_demotions)} | "
            f"Weights updated: {self.weights_updated} | "
            f"Cache purged: {self.cache_purged} rows"
        )


class MaintenanceEngine:
    """
    Call run() after every search cycle.

    Parameters
    ----------
    db_path         : path to your existing SQLite DB
    response_cache  : optional ResponseCache instance (for TTL purge)
    """

    def __init__(self, db_path: str = "storage/knowledge.db",
                 response_cache=None):
        self.db_path        = db_path
        self.response_cache = response_cache
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ── Schema bootstrap ──────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self) -> None:
        """Add MOM columns to concepts table if they don't exist yet."""
        required_columns = {
            "storage_layer":    "TEXT    NOT NULL DEFAULT 'warm'",
            "last_accessed":    "REAL    NOT NULL DEFAULT 0",
            "search_count":     "INTEGER NOT NULL DEFAULT 0",
            "rediscovery_count":"INTEGER NOT NULL DEFAULT 0",
            "weight":           "REAL    NOT NULL DEFAULT 0.0",
        }
        with self._connect() as conn:
            # Create table if truly absent (first run)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS concepts (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept_name     TEXT    NOT NULL UNIQUE,
                    storage_layer    TEXT    NOT NULL DEFAULT 'warm',
                    last_accessed    REAL    NOT NULL DEFAULT 0,
                    search_count     INTEGER NOT NULL DEFAULT 0,
                    rediscovery_count INTEGER NOT NULL DEFAULT 0,
                    weight           REAL    NOT NULL DEFAULT 0.0
                )
            """)
            # Add missing columns to existing table
            existing = {
                row[1] for row in
                conn.execute("PRAGMA table_info(concepts)").fetchall()
            }
            for col, typedef in required_columns.items():
                if col not in existing:
                    conn.execute(
                        f"ALTER TABLE concepts ADD COLUMN {col} {typedef}"
                    )
                    logger.info("MaintenanceEngine: added column %s to concepts", col)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_concepts_layer
                ON concepts (storage_layer)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_concepts_accessed
                ON concepts (last_accessed)
            """)
            conn.commit()

    # ── ARU weight calculation ────────────────────────────────────────────────

    @staticmethod
    def _compute_weight(search_count: int,
                        last_accessed: float,
                        rediscovery_count: int,
                        now: float,
                        global_max_searches: int = 1) -> float:
        """
        Returns a normalised weight in [0, 1].

        frequency_score  – log-normalised search count
        recency_score    – exponential decay from last access
        rediscovery_score– log-normalised rediscovery count
        """
        # Frequency
        freq_score = (
            math.log1p(search_count) / math.log1p(max(global_max_searches, 1))
        )

        # Recency (exponential decay)
        age = max(now - last_accessed, 0)
        recency_score = math.exp(-RECENCY_DECAY * age)

        # Rediscovery
        redisco_score = math.log1p(rediscovery_count) / math.log1p(
            max(rediscovery_count, 1)
        )

        weight = (
            FREQ_WEIGHT    * freq_score +
            RECENCY_WEIGHT * recency_score +
            REDISCO_WEIGHT * redisco_score
        )
        return min(max(weight, 0.0), 1.0)

    @staticmethod
    def _layer_from_weight(weight: float) -> str:
        if weight >= HOT_THRESHOLD:
            return "hot"
        if weight >= WARM_THRESHOLD:
            return "warm"
        return "cold"

    # ── LRU demotion ─────────────────────────────────────────────────────────

    def _apply_lru_demotions(self, conn: sqlite3.Connection,
                             now: float) -> dict:
        demotions = {}

        # hot → warm if idle too long
        hot_cutoff = now - LRU_HOT_MAX_AGE
        rows = conn.execute("""
            SELECT id, concept_name FROM concepts
            WHERE storage_layer = 'hot' AND last_accessed < ?
        """, (hot_cutoff,)).fetchall()
        for row in rows:
            conn.execute("""
                UPDATE concepts SET storage_layer = 'warm'
                WHERE id = ?
            """, (row["id"],))
            demotions[row["concept_name"]] = "hot→warm (LRU)"
            logger.debug("LRU demote hot→warm: %s", row["concept_name"])

        # warm → cold if idle too long
        warm_cutoff = now - LRU_WARM_MAX_AGE
        rows = conn.execute("""
            SELECT id, concept_name FROM concepts
            WHERE storage_layer = 'warm' AND last_accessed < ?
        """, (warm_cutoff,)).fetchall()
        for row in rows:
            conn.execute("""
                UPDATE concepts SET storage_layer = 'cold'
                WHERE id = ?
            """, (row["id"],))
            demotions[row["concept_name"]] = "warm→cold (LRU)"
            logger.debug("LRU demote warm→cold: %s", row["concept_name"])

        return demotions

    # ── ARU re-ranking ────────────────────────────────────────────────────────

    def _apply_aru_ranking(self, conn: sqlite3.Connection,
                           now: float) -> tuple[dict, dict, int]:
        promotions = {}
        demotions  = {}

        rows = conn.execute("""
            SELECT id, concept_name, storage_layer,
                   search_count, last_accessed, rediscovery_count
            FROM concepts
        """).fetchall()

        if not rows:
            return promotions, demotions, 0

        global_max = max(r["search_count"] for r in rows) or 1

        updates = []
        for row in rows:
            new_weight = self._compute_weight(
                row["search_count"],
                row["last_accessed"],
                row["rediscovery_count"],
                now,
                global_max,
            )
            new_layer = self._layer_from_weight(new_weight)
            old_layer = row["storage_layer"]

            updates.append((new_weight, new_layer, row["id"]))

            if new_layer != old_layer:
                name = row["concept_name"]
                if self._layer_rank(new_layer) > self._layer_rank(old_layer):
                    promotions[name] = f"{old_layer}→{new_layer} (ARU w={new_weight:.2f})"
                else:
                    demotions[name]  = f"{old_layer}→{new_layer} (ARU w={new_weight:.2f})"
                logger.debug("ARU %s→%s: %s (w=%.2f)",
                             old_layer, new_layer, row["concept_name"], new_weight)

        conn.executemany("""
            UPDATE concepts SET weight = ?, storage_layer = ?
            WHERE id = ?
        """, updates)

        return promotions, demotions, len(updates)

    @staticmethod
    def _layer_rank(layer: str) -> int:
        return {"cold": 0, "warm": 1, "hot": 2}.get(layer, 1)

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> MaintenanceReport:
        """
        Execute one full maintenance cycle.
        Call this from your existing runMaintenance() function.
        """
        t0     = time.perf_counter()
        now    = time.time()
        report = MaintenanceReport()

        with self._connect() as conn:
            # Step 1: LRU demotions
            report.lru_demotions = self._apply_lru_demotions(conn, now)

            # Step 2: ARU re-ranking
            report.aru_promotions, report.aru_demotions, report.weights_updated = \
                self._apply_aru_ranking(conn, now)

            conn.commit()

        # Step 3: Purge stale cache entries (if cache is wired in)
        if self.response_cache is not None:
            report.cache_purged = self.response_cache.purge_expired()

        report.duration_ms = (time.perf_counter() - t0) * 1000
        logger.info(report.summary())
        return report

    # ── Utility: record a search hit (call this every time user searches) ─────

    def record_search(self, concept_name: str,
                      is_rediscovery: bool = False) -> None:
        """
        Update search_count, rediscovery_count, and last_accessed for a concept.
        Creates the concept row if it doesn't exist yet.
        """
        now = time.time()
        with self._connect() as conn:
            existing = conn.execute("""
                SELECT id FROM concepts WHERE concept_name = ?
            """, (concept_name,)).fetchone()

            if existing:
                conn.execute("""
                    UPDATE concepts
                    SET search_count      = search_count + 1,
                        rediscovery_count = rediscovery_count + ?,
                        last_accessed     = ?
                    WHERE concept_name = ?
                """, (1 if is_rediscovery else 0, now, concept_name))
            else:
                conn.execute("""
                    INSERT INTO concepts
                        (concept_name, storage_layer, last_accessed,
                         search_count, rediscovery_count, weight)
                    VALUES (?, 'warm', ?, 1, 0, 0.3)
                """, (concept_name, now))
            conn.commit()
        logger.debug("record_search: %s (rediscovery=%s)", concept_name, is_rediscovery)
