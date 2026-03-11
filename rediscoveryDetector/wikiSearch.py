import requests

WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"

HEADERS = {
    "User-Agent": "KnowledgeCacheBot/1.0 (research project)"
}

def searchWiki(query, limit=5):

    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": limit
    }

    response = requests.get(WIKI_SEARCH_URL, params=params, headers=HEADERS)

    if response.status_code != 200:
        print("Wikipedia API error:", response.status_code)
        return []

    data = response.json()

    results = []
    for item in data["query"]["search"]:
        results.append(item["title"])

    return results


def getWikiSummary(title):

    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + title
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        return ""

    data = response.json()
    return data.get("extract", "")