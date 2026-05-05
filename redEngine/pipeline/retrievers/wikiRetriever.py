import httpx
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

async def retrieveWikipedia(query):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            title = quote(query.replace(" ", "_"), safe="")
            r = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}")

            if r.status_code != 200:
                try:
                    search = await client.get(
                        "https://en.wikipedia.org/w/api.php",
                        params={"action": "query", "list": "search",
                                "srsearch": query, "format": "json", "srlimit": 1}
                    )
                    search_data = search.json()
                except Exception:
                    return []

                results = search_data.get("query", {}).get("search", [])
                if not results:
                    return []

                top_title = quote(results[0]["title"].replace(" ", "_"), safe="")
                try:
                    r = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{top_title}")
                except Exception:
                    return []

                if r.status_code != 200:
                    return []

            try:
                data = r.json()
            except Exception:
                return []

    except Exception as e:
        logger.error("Wikipedia request failed for query '%s': %s", query, e)
        return []

    return [{
        "url":     data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        "title":   data.get("title", ""),
        "content": data.get("extract", "")
    }]