import httpx

async def retrieveWikipedia(query):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}"
        )

        if r.status_code != 200:
            return []

        data = r.json()

        return [{
            "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            "title": data.get("title", ""),
            "content": data.get("extract", "")
        }]