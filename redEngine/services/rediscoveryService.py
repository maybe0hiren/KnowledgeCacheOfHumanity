from redEngine.pipeline.queryGenerator import generateQueries
from redEngine.pipeline.scraper import scrapePages
from redEngine.pipeline.chunker import chunkDocuments
from redEngine.pipeline.embeddings import embedTexts
from redEngine.pipeline.vectorIndex import searchSimilar
from redEngine.pipeline.reranker import rerankResults
from redEngine.llm.reasoning import explainRediscovery


from redEngine.pipeline.retrievers.wikiRetriever import retrieveWikipedia
from redEngine.pipeline.retrievers.arxivRetriever import retrieveArxiv
from redEngine.pipeline.retrievers.semanticScholarRetriever import retrieveSemanticScholar

from storage.dbManager import saveOrUpdateConcept
from storage.maintenanceJob import runMaintenance

async def processIdea(idea):
    saveOrUpdateConcept(idea)
    runMaintenance()
    queries = generateQueries(idea)

    wikiResults = await retrieveWikipedia(idea)
    arxivResults = await retrieveArxiv(idea)
    scholarResults = await retrieveSemanticScholar(idea)

    pages = wikiResults + arxivResults + scholarResults

    chunks = chunkDocuments(pages)

    ideaEmbedding = embedTexts([idea])[0]

    chunkEmbeddings = embedTexts([c["text"] for c in chunks])

    similar = searchSimilar(ideaEmbedding, chunkEmbeddings, chunks)

    reranked = rerankResults(idea, similar)

    explanation = await explainRediscovery(idea, reranked)

    return {
        "matches": reranked,
        "analysis": explanation
    }