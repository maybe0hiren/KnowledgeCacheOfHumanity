"""
HOW TO PLUG MOM INTO YOUR EXISTING SYSTEM
==========================================

Drop the `mom/` folder into the root of KnowledgeCacheOfHumanity (same level
as redEngine/ and storage/). Then follow the patterns below.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. GLOBAL SETUP  (do this once, e.g. in app.py or __init__.py)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from mom.mom_manager import MOMManager

# Points to your existing SQLite DB
mom = MOMManager(
    db_path="storage/knowledge.db",
    custom_ttl={          # optional: override per-source TTL (seconds)
        "web":        21600,   # 6 h
        "wikipedia":  86400,   # 24 h
        "internal":   43200,   # 12 h
        "ai":          3600,   # 1 h
    }
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. REPLACE YOUR EXISTING runMaintenance()
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def runMaintenance():
    """Drop-in replacement – call this after every search cycle."""
    report = mom.maintenance()
    print(report.summary())
    return report


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3A. ALL-IN-ONE PATTERN  (recommended)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def my_web_fetch(concept: str) -> dict:
    """Your real search/fetch logic goes here."""
    # e.g. call Wikipedia API, web scraper, internal KB …
    return {"summary": f"Result for {concept}", "sources": ["example.com"]}

def search(concept: str, source_type: str = "web") -> dict:
    result = mom.handle_search(
        concept=concept,
        source_type=source_type,
        fetch_fn=my_web_fetch,
        search_analysis={"query": concept, "filters": []},
    )
    # After every search, run maintenance
    runMaintenance()
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3B. MANUAL PATTERN  (if you already have your own fetch pipeline)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def search_manual(concept: str, source_type: str = "web") -> dict:
    # 1. Check cache
    cached = mom.get_cached(concept, source_type)
    if cached:
        print(f"[CACHE HIT] Served from DB (age {cached['cache_age_seconds']:.0f}s)")
        runMaintenance()
        return cached["response_data"]

    # 2. Fresh search (your existing logic unchanged)
    fresh_response = my_web_fetch(concept)
    analysis       = {"query": concept, "source_type": source_type}

    # 3. Store in DB
    mom.store_result(
        concept=concept,
        source_type=source_type,
        search_analysis=analysis,
        response_data=fresh_response,
    )

    # 4. Post-search maintenance
    runMaintenance()
    return fresh_response


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. QUICK DEMO (run this file directly to verify everything works)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    import json

    print("=" * 60)
    print("MOM Integration Demo")
    print("=" * 60)

    # Simulate a few searches
    concepts = ["Zero", "Zero", "Zero", "Ancient Clock", "Pi"]

    for concept in concepts:
        print(f"\n→ Searching: {concept!r}")
        result = search(concept, source_type="web")
        src = "CACHE" if result.get("from_cache") else "FRESH"
        print(f"  [{src}] response_data = {json.dumps(result.get('response_data', result), indent=2)[:80]}…")

    print("\n" + "=" * 60)
    print("Cache Stats:")
    print(json.dumps(mom.cache_stats(), indent=2))

    print("\n" + "=" * 60)
    print("Final Maintenance Run:")
    report = runMaintenance()
    print(f"  LRU demotions : {report.lru_demotions}")
    print(f"  ARU promotions: {report.aru_promotions}")
    print(f"  ARU demotions : {report.aru_demotions}")
    print(f"  Weights updated: {report.weights_updated}")
