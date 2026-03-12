from scrapling.fetchers import Fetcher

async def scrapePages(results):

    pages = []

    for r in results:

        try:
            page = Fetcher.get(r["url"])
            text = page.text

            pages.append({
                "url": r["url"],
                "title": r["title"],
                "content": text
            })

        except:
            continue

    return pages