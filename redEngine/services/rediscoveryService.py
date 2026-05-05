from redEngine.pipeline.queryGenerator import generateQueries
from redEngine.pipeline.chunker import chunkDocuments
from redEngine.pipeline.embeddings import embedTexts
from redEngine.pipeline.vectorIndex import searchSimilar
from redEngine.pipeline.reranker import rerankResults
from redEngine.llm.reasoning import explainRediscovery

from redEngine.pipeline.retrievers.wikiRetriever import retrieveWikipedia
from redEngine.pipeline.retrievers.arxivRetriever import retrieveArxiv
from redEngine.pipeline.retrievers.semanticScholarRetriever import retrieveSemanticScholar

from storage.dbManager import saveOrUpdateConcept, saveConceptResources


async def processIdea(idea: str, registry) -> dict:
    saveOrUpdateConcept(idea)
    registry.engine.record_search(idea)

    generateQueries(idea)

    # ── Cached retrieval ──────────────────────────────────────────────────────
    wiki_hit    = registry.get_cached(idea, "wikipedia")
    arxiv_hit   = registry.get_cached(idea, "arxiv")
    scholar_hit = registry.get_cached(idea, "semantic_scholar")

    wikiResults    = wiki_hit["response_data"]    if wiki_hit    else await retrieveWikipedia(idea)
    arxivResults   = arxiv_hit["response_data"]   if arxiv_hit   else await retrieveArxiv(idea)
    scholarResults = scholar_hit["response_data"] if scholar_hit else await retrieveSemanticScholar(idea)

    # Cache may return {} instead of [] — normalise to list
    if not isinstance(wikiResults, list):    wikiResults    = []
    if not isinstance(arxivResults, list):   arxivResults   = []
    if not isinstance(scholarResults, list): scholarResults = []

    if not wiki_hit:
        registry.store_result(idea, "wikipedia",        response_data=wikiResults)
    if not arxiv_hit:
        registry.store_result(idea, "arxiv",            response_data=arxivResults)
    if not scholar_hit:
        registry.store_result(idea, "semantic_scholar", response_data=scholarResults)
    # ─────────────────────────────────────────────────────────────────────────

    resources = (
        [{"resource_type": "wikipedia",        "title": r.get("title", ""), "url": r.get("url", "")} for r in wikiResults]  +
        [{"resource_type": "arxiv",            "title": r.get("title", ""), "url": r.get("url", "")} for r in arxivResults] +
        [{"resource_type": "semantic_scholar", "title": r.get("title", ""), "url": r.get("url", "")} for r in scholarResults]
    )
    saveConceptResources(idea, resources)

    pages  = wikiResults + arxivResults + scholarResults
    chunks = chunkDocuments(pages)

    if chunks:
        ideaEmbedding   = embedTexts([idea])[0]
        chunkEmbeddings = embedTexts([c["text"] for c in chunks])
        similar  = searchSimilar(ideaEmbedding, chunkEmbeddings, chunks)
        reranked = rerankResults(idea, similar)
    else:
        reranked = []

    explanation = await explainRediscovery(idea, reranked)

    registry.run_maintenance()

    return {
        "matches":   reranked,
        "analysis":  explanation,
        "resources": resources,
    }