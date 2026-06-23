Knowledge Cache of Humanity
============================

An AI-powered knowledge engine that searches, analyzes, and caches human ideas — preventing the repeated rediscovery of concepts across generations.

* * *

INTRODUCTION
------------

KCH models civilization's knowledge as a memory hierarchy, inspired by how computer systems manage data using cache tiers. Frequently accessed ideas stay hot; unused ideas cool down to cold storage.

Instead of generic AI answers, KCH retrieves real content from Wikipedia, arXiv, and Semantic Scholar before generating a structured response — no hallucinations.

* * *

ARCHITECTURE
------------

1.  User submits a concept via the web interface (JWT authenticated)
2.  Wikipedia, arXiv, and Semantic Scholar are queried simultaneously using asyncio.gather()
3.  Results are split into 500-word chunks with source URL and title metadata
4.  Chunks are embedded using all-mpnet-base-v2 (768-dim) and searched via FAISS
5.  CrossEncoder reranks top 10 results down to top 5 by relevance
6.  Gemini Flash Lite generates a structured multi-paragraph analysis
7.  Global + Indian startup ecosystem fetched via Gemini in parallel with step 6
8.  Concept is stored in SQLite and assigned a Hot / Warm / Cold cache tier based on usage

* * *

CACHE TIERS
-----------

| Tier | Weight Threshold | Condition |
|------|-----------------|-----------|
| Hot  | >= 80 | Frequently and recently accessed |
| Warm | >= 30 | Moderately active |
| Cold | < 30  | Not accessed for 14+ days |

*   Weight = frequency × 0.5 + recency × 0.3 + rediscovery × 0.2
*   Hot demotes to Warm after 3 days without access
*   Warm demotes to Cold after 14 days without access

* * *

TECH STACK
----------

| Layer | Technology |
|-------|------------|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| AI / LLM | Google Gemini Flash Lite (google-generativeai) |
| Embeddings | Sentence Transformers — all-mpnet-base-v2 (768-dim) |
| Vector Search | FAISS — IndexFlatL2, in-memory |
| Reranker | CrossEncoder — ms-marco-MiniLM-L-6-v2 |
| Keyword Extraction | KeyBERT |
| Database | SQLite × 3 — auth.db, database.db, knowledge.db |
| Frontend | HTML, CSS, Vanilla JavaScript |

* * *

PYTHON PACKAGES REQUIRED
------------------------

Install dependencies:

    pip install fastapi uvicorn google-generativeai sentence-transformers faiss-cpu keybert httpx feedparser sqlalchemy python-dotenv numpy

* * *

ENVIRONMENT VARIABLES
---------------------

Create a .env file in the project root:

    GEMINI_API_KEY=your_gemini_api_key

Get a free key at https://aistudio.google.com/apikey


* * *
