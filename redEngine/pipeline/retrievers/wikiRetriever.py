import httpx
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "KnowledgeCacheOfHumanity/1.0 (kch-project@example.com)"}
_API     = "https://en.wikipedia.org/w/api.php"


async def retrieveWikipedia(query):
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS) as client:

            # Step 1: find the best-matching article title
            search_r = await client.get(_API, params={
                "action": "query", "list": "search",
                "srsearch": query, "format": "json", "srlimit": 1,
            })
            if search_r.status_code != 200:
                return []

            results = search_r.json().get("query", {}).get("search", [])
            if not results:
                return []

            title = results[0]["title"]

            # Step 2: fetch the intro extract for that title
            extract_r = await client.get(_API, params={
                "action":      "query",
                "titles":      title,
                "prop":        "extracts",
                "exintro":     True,
                "explaintext": True,
                "redirects":   1,
                "format":      "json",
            })
            if extract_r.status_code != 200:
                return []

            pages = extract_r.json().get("query", {}).get("pages", {})
            for pid, page in pages.items():
                if pid == "-1" or "missing" in page:
                    return []
                page_title = page.get("title", "")
                page_url   = (
                    f"https://en.wikipedia.org/wiki/"
                    f"{quote(page_title.replace(' ', '_'), safe='')}"
                )
                return [{
                    "url":     page_url,
                    "title":   page_title,
                    "content": page.get("extract", ""),
                }]

    except Exception as e:
        logger.error("Wikipedia request failed for query '%s': %s", query, e)

    return []
