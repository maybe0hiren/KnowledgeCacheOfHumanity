from pipeline.queryGenerator import generateQueries
from pipeline.retriever import retrieveSources
from pipeline.scraper import scrapePages
from pipeline.chunker import chunkDocuments
from pipeline.embeddings import embedTexts
from pipeline.vectorIndex import searchSimilar
from pipeline.reranker import rerankResults
from llm.reasoning import explainRediscovery

async def processIdea(idea):

    queries = generateQueries(idea)

    searchResults = await retrieveSources(queries)

    pages = await scrapePages(searchResults)

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