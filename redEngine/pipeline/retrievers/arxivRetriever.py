import httpx
import feedparser

async def retrieveArxiv(query):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "http://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": 5
            }
        )

    feed = feedparser.parse(r.text)

    results = []

    for entry in feed.entries:
        results.append({
            "url": entry.link,
            "title": entry.title,
            "content": entry.summary
        })

    return results