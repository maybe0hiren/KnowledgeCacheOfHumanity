# redEngine/services/rediscoveryService.py  (after change)
from redEngine.pipeline.queryGenerator import generateQueries
from redEngine.pipeline.chunker import chunkDocuments
from redEngine.pipeline.embeddings import embedTexts
from redEngine.pipeline.vectorIndex import searchSimilar
from redEngine.pipeline.reranker import rerankResults
from redEngine.llm.reasoning import explainRediscovery

from redEngine.pipeline.retrievers.wikiRetriever import retrieveWikipedia
from redEngine.pipeline.retrievers.arxivRetriever import retrieveArxiv
from redEngine.pipeline.retrievers.semanticScholarRetriever import retrieveSemanticScholar

from storage.dbManager import saveOrUpdateConcept  # keep existing SQLAlchemy layer


async def processIdea(idea, mom):                  # ← accept mom
    saveOrUpdateConcept(idea)                      # unchanged — keeps existing DB
    mom.engine.record_search(idea)                 # ← tell MOM this concept was accessed

    queries = generateQueries(idea)

    # ── Cached retrieval ──────────────────────────────────────────────────────
    async def fetch_wiki(_):
        return await retrieveWikipedia(idea)

    async def fetch_arxiv(_):
        return await retrieveArxiv(idea)

    async def fetch_scholar(_):
        return await retrieveSemanticScholar(idea)

    wiki_hit    = mom.get_cached(idea, "wikipedia")
    arxiv_hit   = mom.get_cached(idea, "arxiv")
    scholar_hit = mom.get_cached(idea, "semantic_scholar")

    wikiResults    = wiki_hit["response_data"]    if wiki_hit    else await retrieveWikipedia(idea)
    arxivResults   = arxiv_hit["response_data"]   if arxiv_hit   else await retrieveArxiv(idea)
    scholarResults = scholar_hit["response_data"] if scholar_hit else await retrieveSemanticScholar(idea)

    if not wiki_hit:
        mom.store_result(idea, "wikipedia",    response_data=wikiResults)
    if not arxiv_hit:
        mom.store_result(idea, "arxiv",        response_data=arxivResults)
    if not scholar_hit:
        mom.store_result(idea, "semantic_scholar", response_data=scholarResults)
    # ─────────────────────────────────────────────────────────────────────────

    pages = wikiResults + arxivResults + scholarResults
    chunks = chunkDocuments(pages)

    ideaEmbedding  = embedTexts([idea])[0]
    chunkEmbeddings = embedTexts([c["text"] for c in chunks])

    similar  = searchSimilar(ideaEmbedding, chunkEmbeddings, chunks)
    reranked = rerankResults(idea, similar)
    explanation = await explainRediscovery(idea, reranked)

    mom.maintenance()                              # ← replaces runMaintenance()

    return {
        "matches":  reranked,
        "analysis": explanation
    }