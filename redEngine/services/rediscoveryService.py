import logging
import traceback

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

logger = logging.getLogger(__name__)


async def processIdea(idea: str, registry) -> dict:
    # ── 1. Save concept (non-critical — don't let it block everything) ───
    try:
        saveOrUpdateConcept(idea)
    except Exception:
        logger.error("saveOrUpdateConcept failed:\n%s", traceback.format_exc())

    try:
        registry.engine.record_search(idea)
    except Exception:
        logger.error("registry.record_search failed:\n%s", traceback.format_exc())

    # ── 2. Generate keyword queries (non-critical) ───────────────────────
    try:
        generateQueries(idea)
    except Exception:
        logger.error("generateQueries failed:\n%s", traceback.format_exc())

    # ── 3. Retrieve from sources ─────────────────────────────────────────
    wikiResults = []
    arxivResults = []
    scholarResults = []

    try:
        wiki_hit = registry.get_cached(idea, "wikipedia")
        if wiki_hit:
            wikiResults = wiki_hit["response_data"]
        else:
            wikiResults = await retrieveWikipedia(idea)
            registry.store_result(idea, "wikipedia", response_data=wikiResults)
    except Exception:
        logger.error("Wikipedia retrieval failed:\n%s", traceback.format_exc())

    try:
        arxiv_hit = registry.get_cached(idea, "arxiv")
        if arxiv_hit:
            arxivResults = arxiv_hit["response_data"]
        else:
            arxivResults = await retrieveArxiv(idea)
            registry.store_result(idea, "arxiv", response_data=arxivResults)
    except Exception:
        logger.error("arXiv retrieval failed:\n%s", traceback.format_exc())

    try:
        scholar_hit = registry.get_cached(idea, "semantic_scholar")
        if scholar_hit:
            scholarResults = scholar_hit["response_data"]
        else:
            scholarResults = await retrieveSemanticScholar(idea)
            registry.store_result(idea, "semantic_scholar", response_data=scholarResults)
    except Exception:
        logger.error("Semantic Scholar retrieval failed:\n%s", traceback.format_exc())

    # Normalise — cache can return {} instead of []
    if not isinstance(wikiResults, list):    wikiResults = []
    if not isinstance(arxivResults, list):   arxivResults = []
    if not isinstance(scholarResults, list): scholarResults = []

    logger.info("Retrieved: %d wiki, %d arxiv, %d scholar results",
                len(wikiResults), len(arxivResults), len(scholarResults))

    # ── 4. Build resources list ──────────────────────────────────────────
    resources = (
        [{"resource_type": "wikipedia",        "title": r.get("title", ""), "url": r.get("url", "")} for r in wikiResults]  +
        [{"resource_type": "arxiv",            "title": r.get("title", ""), "url": r.get("url", "")} for r in arxivResults] +
        [{"resource_type": "semantic_scholar", "title": r.get("title", ""), "url": r.get("url", "")} for r in scholarResults]
    )

    try:
        saveConceptResources(idea, resources)
    except Exception:
        logger.error("saveConceptResources failed:\n%s", traceback.format_exc())

    # ── 5. Chunk → embed → search → rerank ───────────────────────────────
    reranked = []
    try:
        pages = wikiResults + arxivResults + scholarResults
        chunks = chunkDocuments(pages)
        logger.info("Chunked %d pages into %d chunks", len(pages), len(chunks))

        if chunks:
            ideaEmbedding   = embedTexts([idea])[0]
            chunkEmbeddings = embedTexts([c["text"] for c in chunks])
            similar  = searchSimilar(ideaEmbedding, chunkEmbeddings, chunks)
            reranked = rerankResults(idea, similar)
            logger.info("Reranked to %d matches", len(reranked))
    except Exception:
        logger.error("Chunk/embed/rerank failed:\n%s", traceback.format_exc())

    # ── 6. LLM explanation ───────────────────────────────────────────────
    explanation = ""
    try:
        explanation = await explainRediscovery(idea, reranked)
        logger.info("Analysis generated (%d chars)", len(explanation) if explanation else 0)
    except Exception:
        logger.error("explainRediscovery failed:\n%s", traceback.format_exc())

    if not explanation:
        explanation = (
            f"The concept '{idea}' has been recorded and matched against historical knowledge sources. "
            f"We found {len(resources)} related resources from Wikipedia, arXiv, and Semantic Scholar. "
            f"A detailed AI-generated explanation could not be produced at this time, but the sources "
            f"listed below provide relevant context and background for this idea."
        )

    # ── 7. Maintenance (non-critical) ────────────────────────────────────
    try:
        registry.run_maintenance()
    except Exception:
        logger.error("Maintenance failed:\n%s", traceback.format_exc())

    # ── 8. Always return a valid response ────────────────────────────────
    result = {
        "matches":   reranked,
        "analysis":  explanation,
        "resources": resources,
    }
    logger.info("Returning response: %d matches, %d resources, analysis=%s",
                len(reranked), len(resources), bool(explanation))
    return result
