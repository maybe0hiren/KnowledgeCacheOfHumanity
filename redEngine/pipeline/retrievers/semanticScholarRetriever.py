import httpx

async def retrieveSemanticScholar(query):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query": query,
                "limit": 5,
                "fields": "title,abstract,url"
            }
        )

        data = r.json()

    results = []

    for paper in data.get("data", []):
        results.append({
            "url": paper.get("url", ""),
            "title": paper.get("title", ""),
            "content": paper.get("abstract", "")
        })

    return results