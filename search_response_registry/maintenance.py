import sqlite3
import time
import math
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

HOT_THRESHOLD  = 0.65
WARM_THRESHOLD = 0.30
LRU_HOT_MAX_AGE  = 60 * 60 * 24 * 3
LRU_WARM_MAX_AGE = 60 * 60 * 24 * 14
FREQ_WEIGHT    = 0.45
RECENCY_WEIGHT = 0.35
REDISCO_WEIGHT = 0.20
RECENCY_DECAY  = 0.0001


@dataclass
class MaintenanceReport:
    lru_demotions:   dict  = field(default_factory=dict)
    aru_promotions:  dict  = field(default_factory=dict)
    aru_demotions:   dict  = field(default_factory=dict)
    weights_updated: int   = 0
    cache_purged:    int   = 0
    duration_ms:     float = 0.0

    def summary(self) -> str:
        return (f"Maintenance done in {self.duration_ms:.1f}ms | LRU demotions: {len(self.lru_demotions)} | "
                f"ARU promotions: {len(self.aru_promotions)} | ARU demotions: {len(self.aru_demotions)} | "
                f"Weights updated: {self.weights_updated} | Cache purged: {self.cache_purged} rows")


class MaintenanceEngine:

    def __init__(self, db_path: str = "storage/knowledge.db", response_cache=None):
        self.db_path        = db_path
        self.response_cache = response_cache
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS concepts (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept_name      TEXT    NOT NULL UNIQUE,
                    storage_layer     TEXT    NOT NULL DEFAULT 'warm',
                    last_accessed     REAL    NOT NULL DEFAULT 0,
                    search_count      INTEGER NOT NULL DEFAULT 0,
                    rediscovery_count INTEGER NOT NULL DEFAULT 0,
                    weight            REAL    NOT NULL DEFAULT 0.0
                )
            """)
            existing = {row[1] for row in conn.execute("PRAGMA table_info(concepts)").fetchall()}
            for col, typedef in {
                "storage_layer": "TEXT NOT NULL DEFAULT 'warm'",
                "last_accessed": "REAL NOT NULL DEFAULT 0",
                "search_count":  "INTEGER NOT NULL DEFAULT 0",
                "rediscovery_count": "INTEGER NOT NULL DEFAULT 0",
                "weight": "REAL NOT NULL DEFAULT 0.0",
            }.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE concepts ADD COLUMN {col} {typedef}")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_concepts_layer ON concepts (storage_layer)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_concepts_accessed ON concepts (last_accessed)")
            conn.commit()

    @staticmethod
    def _compute_weight(search_count, last_accessed, rediscovery_count, now, global_max_searches=1):
        freq_score    = math.log1p(search_count) / math.log1p(max(global_max_searches, 1))
        recency_score = math.exp(-RECENCY_DECAY * max(now - last_accessed, 0))
        redisco_score = math.log1p(rediscovery_count) / math.log1p(max(rediscovery_count, 1))
        return min(max(FREQ_WEIGHT * freq_score + RECENCY_WEIGHT * recency_score + REDISCO_WEIGHT * redisco_score, 0.0), 1.0)

    @staticmethod
    def _layer_from_weight(weight):
        if weight >= HOT_THRESHOLD:  return "hot"
        if weight >= WARM_THRESHOLD: return "warm"
        return "cold"

    @staticmethod
    def _layer_rank(layer):
        return {"cold": 0, "warm": 1, "hot": 2}.get(layer, 1)

    def _apply_lru_demotions(self, conn, now):
        demotions = {}
        for row in conn.execute("SELECT id, concept_name FROM concepts WHERE storage_layer = 'hot' AND last_accessed < ?", (now - LRU_HOT_MAX_AGE,)).fetchall():
            conn.execute("UPDATE concepts SET storage_layer = 'warm' WHERE id = ?", (row["id"],))
            demotions[row["concept_name"]] = "hot→warm (LRU)"
        for row in conn.execute("SELECT id, concept_name FROM concepts WHERE storage_layer = 'warm' AND last_accessed < ?", (now - LRU_WARM_MAX_AGE,)).fetchall():
            conn.execute("UPDATE concepts SET storage_layer = 'cold' WHERE id = ?", (row["id"],))
            demotions[row["concept_name"]] = "warm→cold (LRU)"
        return demotions

    def _apply_aru_ranking(self, conn, now):
        rows = conn.execute("SELECT id, concept_name, storage_layer, search_count, last_accessed, rediscovery_count FROM concepts").fetchall()
        if not rows:
            return {}, {}, 0
        global_max = max(r["search_count"] for r in rows) or 1
        promotions, demotions, updates = {}, {}, []
        for row in rows:
            new_weight = self._compute_weight(row["search_count"], row["last_accessed"], row["rediscovery_count"], now, global_max)
            new_layer  = self._layer_from_weight(new_weight)
            old_layer  = row["storage_layer"]
            updates.append((new_weight, new_layer, row["id"]))
            if new_layer != old_layer:
                name = row["concept_name"]
                if self._layer_rank(new_layer) > self._layer_rank(old_layer):
                    promotions[name] = f"{old_layer}→{new_layer}"
                else:
                    demotions[name]  = f"{old_layer}→{new_layer}"
        conn.executemany("UPDATE concepts SET weight = ?, storage_layer = ? WHERE id = ?", updates)
        return promotions, demotions, len(updates)

    def run(self) -> MaintenanceReport:
        t0, now, report = time.perf_counter(), time.time(), MaintenanceReport()
        with self._connect() as conn:
            report.lru_demotions = self._apply_lru_demotions(conn, now)
            report.aru_promotions, report.aru_demotions, report.weights_updated = self._apply_aru_ranking(conn, now)
            conn.commit()
        if self.response_cache is not None:
            report.cache_purged = self.response_cache.purge_expired()
        report.duration_ms = (time.perf_counter() - t0) * 1000
        return report

    def record_search(self, concept_name: str, is_rediscovery: bool = False) -> None:
        now = time.time()
        with self._connect() as conn:
            existing = conn.execute("SELECT id FROM concepts WHERE concept_name = ?", (concept_name,)).fetchone()
            if existing:
                conn.execute("""
                    UPDATE concepts SET search_count = search_count + 1,
                    rediscovery_count = rediscovery_count + ?, last_accessed = ?
                    WHERE concept_name = ?
                """, (1 if is_rediscovery else 0, now, concept_name))
            else:
                conn.execute("INSERT INTO concepts (concept_name, storage_layer, last_accessed, search_count, rediscovery_count, weight) VALUES (?, 'warm', ?, 1, 0, 0.3)", (concept_name, now))
            conn.commit()