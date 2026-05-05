import httpx
import logging

logger = logging.getLogger(__name__)

async def retrieveSemanticScholar(query):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={"query": query, "limit": 5, "fields": "title,abstract,url"}
            )

        if r.status_code != 200:
            logger.warning("Semantic Scholar returned status %s for query: %s", r.status_code, query)
            return []

        try:
            data = r.json()
        except Exception:
            return []

    except Exception as e:
        logger.error("Semantic Scholar request failed for query '%s': %s", query, e)
        return []

    results = []
    for paper in data.get("data", []):
        results.append({
            "url":     paper.get("url", ""),
            "title":   paper.get("title", ""),
            "content": paper.get("abstract", "")
        })

    return results