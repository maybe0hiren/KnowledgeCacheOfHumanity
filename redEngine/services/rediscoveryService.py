import asyncio
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

from storage.dbManager import saveOrUpdateConcept, saveConceptResources, getCachedAnalysis

logger = logging.getLogger(__name__)


async def processIdea(idea: str, registry) -> dict:
    # concept_name will be extracted from LLM response later; use idea as fallback
    concept_name = idea

    try:
        registry.engine.record_search(concept_name)
    except Exception:
        logger.error("registry.record_search failed:\n%s", traceback.format_exc())

    # ── 2. Generate keyword queries (non-critical) ───────────────────────
    try:
        generateQueries(idea)
    except Exception:
        logger.error("generateQueries failed:\n%s", traceback.format_exc())

    # ── 3. Retrieve from all sources in parallel ─────────────────────────
    async def _fetch_wiki():
        try:
            hit = registry.get_cached(idea, "wikipedia")
            if hit:
                return hit["response_data"]
        except Exception:
            logger.warning("Registry cache read failed for wikipedia, falling back to live fetch")
        results = await retrieveWikipedia(idea)
        try:
            registry.store_result(idea, "wikipedia", response_data=results)
        except Exception:
            logger.warning("Registry cache write failed for wikipedia")
        return results

    async def _fetch_arxiv():
        try:
            hit = registry.get_cached(idea, "arxiv")
            if hit:
                return hit["response_data"]
        except Exception:
            logger.warning("Registry cache read failed for arxiv, falling back to live fetch")
        results = await retrieveArxiv(idea)
        try:
            registry.store_result(idea, "arxiv", response_data=results)
        except Exception:
            logger.warning("Registry cache write failed for arxiv")
        return results

    async def _fetch_scholar():
        try:
            hit = registry.get_cached(idea, "semantic_scholar")
            if hit:
                return hit["response_data"]
        except Exception:
            logger.warning("Registry cache read failed for semantic_scholar, falling back to live fetch")
        results = await retrieveSemanticScholar(idea)
        try:
            registry.store_result(idea, "semantic_scholar", response_data=results)
        except Exception:
            logger.warning("Registry cache write failed for semantic_scholar")
        return results

    wiki_res, arxiv_res, scholar_res = await asyncio.gather(
        _fetch_wiki(), _fetch_arxiv(), _fetch_scholar(),
        return_exceptions=True
    )

    wikiResults    = wiki_res    if isinstance(wiki_res,    list) else []
    arxivResults   = arxiv_res   if isinstance(arxiv_res,   list) else []
    scholarResults = scholar_res if isinstance(scholar_res, list) else []

    if isinstance(wiki_res, Exception):
        logger.error("Wikipedia retrieval failed: %s", wiki_res)
    if isinstance(arxiv_res, Exception):
        logger.error("arXiv retrieval failed: %s", arxiv_res)
    if isinstance(scholar_res, Exception):
        logger.error("Semantic Scholar retrieval failed: %s", scholar_res)

    logger.info("Retrieved: %d wiki, %d arxiv, %d scholar results",
                len(wikiResults), len(arxivResults), len(scholarResults))

    # ── 4. Build resources list (saved to DB later after name is extracted) ─
    resources = (
        [{"resource_type": "wikipedia",        "title": r.get("title", ""), "url": r.get("url", "")} for r in wikiResults]  +
        [{"resource_type": "arxiv",            "title": r.get("title", ""), "url": r.get("url", "")} for r in arxivResults] +
        [{"resource_type": "semantic_scholar", "title": r.get("title", ""), "url": r.get("url", "")} for r in scholarResults]
    )

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

    # ── 6. LLM explanation (with cache) ─────────────────────────────────
    explanation = ""

    # Check DB for a previously generated analysis for this idea
    cached_analysis = None
    try:
        cached_analysis = getCachedAnalysis(idea)
        if cached_analysis:
            logger.info("Analysis cache hit for '%s' — skipping Gemini call", idea)
    except Exception:
        logger.error("getCachedAnalysis failed:\n%s", traceback.format_exc())

    gemini_succeeded = False
    if cached_analysis:
        explanation = cached_analysis
    else:
        try:
            explanation = await explainRediscovery(idea, reranked)
            if explanation:
                gemini_succeeded = True
                logger.info("Analysis generated (%d chars)", len(explanation))
        except Exception:
            logger.error("explainRediscovery failed:\n%s", traceback.format_exc())

    if not explanation:
        explanation = (
            f"The concept '{idea}' has been recorded and matched against historical knowledge sources. "
            f"We found {len(resources)} related resources from Wikipedia, arXiv, and Semantic Scholar. "
            f"A detailed AI-generated explanation could not be produced at this time, but the sources "
            f"listed below provide relevant context and background for this idea."
        )

    # ── 7. Extract concept name from "ConceptName: explanation" format ───
    analysis_body = explanation
    first_line = explanation.split("\n")[0]
    if ": " in first_line:
        parts = first_line.split(": ", 1)
        extracted = parts[0].strip().strip("*").strip()
        # Accept as concept name if it's a reasonable length (not a full sentence)
        if 1 <= len(extracted.split()) <= 6:
            concept_name = extracted
            analysis_body = explanation  # keep full text including name line
            logger.info("Extracted concept name: '%s'", concept_name)

    # ── 8. Save concept with extracted name + original description ───────
    # Only cache analysis when Gemini actually succeeded — never cache fallback text
    try:
        saveOrUpdateConcept(
            concept_name,
            description=idea,
            analysis=explanation if gemini_succeeded else "",
        )
    except Exception:
        logger.error("saveOrUpdateConcept failed:\n%s", traceback.format_exc())

    try:
        saveConceptResources(concept_name, resources)
    except Exception:
        logger.error("saveConceptResources failed:\n%s", traceback.format_exc())

    # ── 9. Maintenance (non-critical) ────────────────────────────────────
    try:
        registry.run_maintenance()
    except Exception:
        logger.error("Maintenance failed:\n%s", traceback.format_exc())

    # ── 10. Always return a valid response ───────────────────────────────
    result = {
        "concept_name": concept_name,
        "matches":      reranked,
        "analysis":     analysis_body,
        "resources":    resources,
    }
    logger.info("Returning response: concept='%s', %d matches, %d resources",
                concept_name, len(reranked), len(resources))
    return result
