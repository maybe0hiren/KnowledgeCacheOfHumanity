Knowledge Cache of Humanity
===========================

An AI-powered knowledge engine that searches, analyzes, and caches human ideas — preventing the repeated rediscovery of important concepts across generations.

* * *

INTRODUCTION
------------

Knowledge Cache of Humanity (KCH) models human civilization as a memory hierarchy, inspired by how computer systems manage data using cache structures. Frequently accessed ideas stay in active cache; rarely used ideas move to archival storage.

KCH helps students, researchers, and curious minds instantly understand any concept by asking questions such as:

*   What is the origin of zero?
*   Who first described gravity?
*   How has quantum mechanics evolved over time?
*   What startups are working in this space today?

Instead of generic AI answers, KCH retrieves the most relevant content from Wikipedia, arXiv, and Semantic Scholar before generating a structured response.

* * *

ARCHITECTURE
------------

KCH follows a Retrieval-Augmented Generation (RAG) workflow with a smart caching layer:

1.  User Submission

    *   User submits any concept or idea via the web interface
    *   JWT-authenticated session ensures secure, personalized access

2.  Parallel Retrieval

    *   Wikipedia, arXiv, and Semantic Scholar are queried simultaneously using asyncio.gather()
    *   Results are cached in a SHA-256 keyed SQLite store with per-source TTLs:
        *   Wikipedia: 24 hours
        *   arXiv: 12 hours
        *   Semantic Scholar: 12 hours

3.  Chunking

    *   Retrieved documents are split into 500-word sliding windows
    *   Source URL and title metadata is preserved per chunk

4.  Embedding + Vector Search

    *   Chunks are embedded using all-mpnet-base-v2 (768-dimensional dense vectors)
    *   FAISS IndexFlatL2 performs in-memory similarity search to retrieve top 10 chunks
    *   CrossEncoder ms-marco-MiniLM-L-6-v2 reranks results to top 5 by relevance

5.  LLM Analysis

    *   Google Gemini Flash Lite generates a structured multi-paragraph explanation
    *   Response begins with the canonical concept name in "ConceptName: explanation" format
    *   Analysis runs in parallel with startup ecosystem lookup to reduce total latency

6.  Smart Caching (Hot / Warm / Cold Tiers)

    *   Every concept is stored in SQLite with frequency, recency, and rediscovery metrics
    *   A composite weight score determines the storage tier:
        *   Hot: weight >= 80 (frequently and recently accessed)
        *   Warm: weight >= 30 (moderately active)
        *   Cold: weight < 30 (not accessed for an extended period)
    *   LRU demotion rules:
        *   Hot to Warm after 3 days without access
        *   Warm to Cold after 14 days without access

7.  Startup Ecosystem

    *   Gemini returns a list of real Global and Indian startups working in the searched concept's space
    *   Results include company name and country tag

* * *

TECH STACK
----------

*   Python 3.10+
*   FastAPI + Uvicorn
*   Google Gemini API (google-generativeai)
*   Sentence Transformers (all-mpnet-base-v2)
*   FAISS (faiss-cpu)
*   KeyBERT
*   SQLite (auth.db + database.db + knowledge.db)
*   HTML + CSS + Vanilla JavaScript

* * *

PYTHON PACKAGES REQUIRED
------------------------

Install dependencies:

pip install fastapi
pip install uvicorn
pip install google-generativeai
pip install sentence-transformers
pip install faiss-cpu
pip install keybert
pip install httpx
pip install feedparser
pip install sqlalchemy
pip install python-dotenv
pip install numpy

* * *

ENVIRONMENT VARIABLES
---------------------

Create a .env file in the project root:

GEMINI_API_KEY=your_gemini_api_key

Get your free Gemini API key at https://aistudio.google.com/apikey

* * *

RUNNING THE PROJECT
-------------------

Start the server:

uvicorn redEngine.api.app:app --host 127.0.0.1 --port 8080 --reload

Open in browser:

http://127.0.0.1:8080

* * *

API USAGE
---------

Sign Up

curl -X POST "http://127.0.0.1:8080/auth/signup"
-H "Content-Type: application/json"
-d '{ "username": "yourname", "email": "your@email.com", "password": "Pass@1234" }'

Sign In

curl -X POST "http://127.0.0.1:8080/auth/login"
-H "Content-Type: application/json"
-d '{ "username": "yourname", "password": "Pass@1234" }'

Analyze a Concept

curl -X POST "http://127.0.0.1:8080/analyze"
-H "Content-Type: application/json"
-H "Authorization: Bearer YOUR_SESSION_TOKEN"
-d '{ "idea": "invention of zero" }'

Response:

{ "concept_name": "Zero", "analysis": "Zero: The concept of zero as a number originated in ancient India...", "matches": [...], "resources": [...], "startups": [{ "name": "Wolfram Alpha", "country": "USA" }] }

Retrieve All Cached Concepts

curl -X GET "http://127.0.0.1:8080/concepts"
-H "Authorization: Bearer YOUR_SESSION_TOKEN"

* * *

FUTURE SCOPE
------------

*   Multi-turn conversation memory per concept
*   Graph-based knowledge relationships between concepts
*   Detect duplicate ideas submitted by different users
*   Browser extension for one-click concept lookup
*   Export personal knowledge cache as PDF or Word
*   Multi-language concept support
