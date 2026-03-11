from ai import getEmbeddings, getSimilarity
from wikiSearch import searchWiki, getWikiSummary

THRESHOLD = 0.85


def detectRediscovery(concept):

    conceptVector = getEmbeddings(concept)

    titles = searchWiki(concept)

    bestMatch = None
    bestScore = 0

    for title in titles:
        summary = getWikiSummary(title)
        if not summary:
            continue
        summaryVector = getEmbeddings(summary)
        score = getSimilarity(conceptVector, summaryVector)
        if score > bestScore:
            bestScore = score
            bestMatch = title


    if bestScore > THRESHOLD:
        return {
            "rediscovered": True,
            "match": bestMatch,
            "similarity": float(bestScore)
        }
    else:
        return {
            "rediscovered": False,
            "match": bestMatch,
            "similarity": float(bestScore)
        }