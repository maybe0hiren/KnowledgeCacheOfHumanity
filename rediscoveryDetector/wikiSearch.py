import requests

WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"

def searchWiki(query, limit=5):
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": limit
    }

    response = requests.get(WIKI_SEARCH_URL, params=params)
    data = response.json()

    results = []
    for item in data["query"]["search"]:
        results.append(item["title"])

    return results


def getWikiSummary(title):

    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + title

    response = requests.get(url)
    data = response.json()

    return data.get("extract", "")