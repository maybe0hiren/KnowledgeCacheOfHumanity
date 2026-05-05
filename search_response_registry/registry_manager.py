import logging
from typing import Any, Callable, Optional

from search_response_registry.response_cache import ResponseCache
from search_response_registry.maintenance import MaintenanceEngine, MaintenanceReport

logger = logging.getLogger(__name__)


class RegistryManager:

    def __init__(self, db_path: str = "storage/knowledge.db", custom_ttl: Optional[dict] = None):
        self.cache  = ResponseCache(db_path, custom_ttl)
        self.engine = MaintenanceEngine(db_path, response_cache=self.cache)

    def get_cached(self, concept: str, source_type: str = "default") -> Optional[dict]:
        return self.cache.get(concept, source_type)

    def store_result(self, concept: str, source_type: str = "default",
                     search_analysis: Any = None, response_data: Any = None,
                     ttl_seconds: Optional[float] = None) -> str:
        return self.cache.set(concept=concept, source_type=source_type,
                              search_analysis=search_analysis, response_data=response_data,
                              ttl_seconds=ttl_seconds)

    def run_maintenance(self) -> MaintenanceReport:
        return self.engine.run()

    def registry_stats(self) -> dict:
        return self.cache.stats()

    def invalidate(self, concept: str, source_type: Optional[str] = None) -> int:
        return self.cache.invalidate(concept, source_type)