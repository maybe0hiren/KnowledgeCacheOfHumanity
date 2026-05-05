import httpx
import feedparser
import logging

logger = logging.getLogger(__name__)

async def retrieveArxiv(query):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "http://export.arxiv.org/api/query",
                params={"search_query": f"all:{query}", "start": 0, "max_results": 5}
            )
    except Exception as e:
        logger.error("arXiv request failed for query '%s': %s", query, e)
        return []

    try:
        feed = feedparser.parse(r.text)
    except Exception:
        return []

    results = []
    for entry in feed.entries:
        try:
            results.append({
                "url":     entry.link,
                "title":   entry.title,
                "content": entry.summary
            })
        except AttributeError:
            continue

    return results