import httpx

async def retrieveSources(queries):

    results = []

    async with httpx.AsyncClient() as client:

        for q in queries:

            r = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": q, "format": "json"}
            )

            data = r.json()

            for topic in data.get("RelatedTopics", []):

                if "FirstURL" in topic:
                    results.append({
                        "url": topic["FirstURL"],
                        "title": topic.get("Text","")
                    })

    return results[:20]