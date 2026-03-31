from pipeline.queryGenerator import generateQueries
from pipeline.scraper import scrapePages
from pipeline.chunker import chunkDocuments
from pipeline.embeddings import embedTexts
from pipeline.vectorIndex import searchSimilar
from pipeline.reranker import rerankResults
from llm.reasoning import explainRediscovery


from pipeline.retrievers.wikiRetriever import retrieveWikipedia
from pipeline.retrievers.arxivRetriever import retrieveArxiv
from pipeline.retrievers.semanticScholarRetriever import retrieveSemanticScholar

async def processIdea(idea):

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