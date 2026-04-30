"""
MOM Manager
===========
Single entry point for the Maintenance & Optimization Module.

Drop-in replacement for your existing runMaintenance() call.

Quick start
-----------
    from mom.mom_manager import MOMManager

    mom = MOMManager(db_path="storage/knowledge.db")

    # Before every search:
    result = mom.handle_search(concept="Zero", source_type="web",
                               fetch_fn=my_search_function)
    # result["response_data"] is either cached or freshly fetched

    # ── or, if you have your own fetch logic ──────────────────────────────
    cached = mom.get_cached("Zero", "web")
    if cached:
        use(cached["response_data"])
    else:
        data = my_search_function("Zero")
        mom.store_result("Zero", "web",
                         search_analysis={"q": "Zero"},
                         response_data=data)

Integration with existing runMaintenance()
------------------------------------------
    # In your existing search handler file:
    from mom.mom_manager import MOMManager
    _mom = MOMManager("storage/knowledge.db")

    def runMaintenance():
        report = _mom.maintenance()
        print(report.summary())
        return report
"""

import logging
import time
from typing import Any, Callable, Optional

from mom.response_cache   import ResponseCache
from mom.maintenance      import MaintenanceEngine, MaintenanceReport

logger = logging.getLogger(__name__)


class MOMManager:
    """
    Unified façade over ResponseCache + MaintenanceEngine.

    Parameters
    ----------
    db_path    : path to the SQLite DB shared with rankingManager.py
    custom_ttl : override per-source-type TTL values (seconds)
                 e.g. {"web": 3600, "wikipedia": 86400}
    """

    def __init__(self,
                 db_path: str = "storage/knowledge.db",
                 custom_ttl: Optional[dict[str, float]] = None):
        self.cache   = ResponseCache(db_path, custom_ttl)
        self.engine  = MaintenanceEngine(db_path, response_cache=self.cache)
        logger.info("MOMManager ready (db=%s)", db_path)

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def get_cached(self, concept: str,
                   source_type: str = "default") -> Optional[dict]:
        """
        Return a cached record if fresh, else None.
        Returned dict has keys: concept, source_type, response_data,
                                search_analysis, cache_age_seconds, serve_count
        """
        return self.cache.get(concept, source_type)

    def store_result(self, concept: str,
                     source_type: str = "default",
                     search_analysis: Any = None,
                     response_data: Any = None,
                     ttl_seconds: Optional[float] = None) -> str:
        """
        Persist a fresh search result to the cache.
        Returns the cache key.
        """
        return self.cache.set(
            concept=concept,
            source_type=source_type,
            search_analysis=search_analysis,
            response_data=response_data,
            ttl_seconds=ttl_seconds,
        )

    # ── All-in-one search handler ─────────────────────────────────────────────

    def handle_search(self,
                      concept: str,
                      source_type: str = "default",
                      fetch_fn: Optional[Callable[[str], Any]] = None,
                      search_analysis: Optional[dict] = None,
                      ttl_seconds: Optional[float] = None) -> dict:
        """
        Full search lifecycle:
            1. Check cache → serve if fresh
            2. If stale / absent → call fetch_fn(concept)
            3. Store fresh result
            4. Record the search hit for ARU ranking
            5. Return unified result dict

        Parameters
        ----------
        concept         : the concept / query string
        source_type     : "web" | "wikipedia" | "internal" | "ai" | "default"
        fetch_fn        : callable(concept) → response_data dict
                          Leave None if you'll store the result yourself.
        search_analysis : optional metadata about the search (keywords, filters)
        ttl_seconds     : override default TTL for this source type

        Returns
        -------
        {
            "concept":          str,
            "source_type":      str,
            "response_data":    dict,
            "search_analysis":  dict,
            "from_cache":       bool,
            "cache_age_seconds": float | None,
            "serve_count":      int,
        }
        """
        # ── 1. Try cache ──────────────────────────────────────────────────────
        cached = self.cache.get(concept, source_type)
        if cached:
            # Still record the hit so LRU / ARU know it was accessed
            is_rediscovery = cached["serve_count"] > 1
            self.engine.record_search(concept, is_rediscovery=is_rediscovery)
            return {**cached, "from_cache": True}

        # ── 2. Fresh fetch ────────────────────────────────────────────────────
        response_data: Any = {}
        if fetch_fn is not None:
            try:
                response_data = fetch_fn(concept)
            except Exception as exc:
                logger.error("fetch_fn failed for %s: %s", concept, exc)
                raise

        # ── 3. Store result ───────────────────────────────────────────────────
        analysis = search_analysis or {"concept": concept, "source_type": source_type}
        self.cache.set(
            concept=concept,
            source_type=source_type,
            search_analysis=analysis,
            response_data=response_data,
            ttl_seconds=ttl_seconds,
        )

        # ── 4. Record for ARU ─────────────────────────────────────────────────
        self.engine.record_search(concept, is_rediscovery=False)

        return {
            "concept":           concept,
            "source_type":       source_type,
            "response_data":     response_data,
            "search_analysis":   analysis,
            "from_cache":        False,
            "cache_age_seconds": 0.0,
            "serve_count":       0,
        }

    # ── Maintenance entry point ───────────────────────────────────────────────

    def maintenance(self) -> MaintenanceReport:
        """
        Run one full maintenance cycle.
        Wire this into your existing runMaintenance() function.

        Example
        -------
            def runMaintenance():
                return mom.maintenance()
        """
        return self.engine.run()

    # ── Admin helpers ─────────────────────────────────────────────────────────

    def cache_stats(self) -> dict:
        """Quick summary of cache state (total, fresh, stale, hits by source)."""
        return self.cache.stats()

    def invalidate(self, concept: str,
                   source_type: Optional[str] = None) -> int:
        """Force-expire cache entries for a concept."""
        return self.cache.invalidate(concept, source_type)
