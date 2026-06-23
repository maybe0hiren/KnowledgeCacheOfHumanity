Knowledge Cache of Humanity
An AI-powered knowledge engine that searches, analyzes, and caches human ideas — preventing repeated rediscovery across generations.

INTRODUCTION
Knowledge Cache of Humanity (KCH) models human civilization as a memory hierarchy, inspired by how computer systems manage data using cache structures. Frequently reused ideas stay in active cache; rarely accessed ideas move to archival storage.

KCH helps students, researchers, and curious minds instantly understand any concept by asking questions such as:

What is the origin of zero?
Who first described gravity?
How has quantum mechanics evolved over time?
What startups are working in this space?

Instead of generic AI answers, KCH retrieves the most relevant content from Wikipedia, arXiv, and Semantic Scholar before generating a structured response.

ARCHITECTURE
KCH follows a Retrieval-Augmented Generation (RAG) workflow with a smart caching layer:

User Submission

User submits any concept or idea via the web interface
JWT-authenticated session ensures secure access

Parallel Retrieval

Wikipedia, arXiv, and Semantic Scholar are queried simultaneously using asyncio.gather()
Results are cached using a SHA-256 keyed SQLite cache with per-source TTLs:
Wikipedia: 24 hours
arXiv: 12 hours
Semantic Scholar: 12 hours

Chunking

Retrieved documents are split into 500-word windows
Source URL and title metadata is preserved per chunk

Embedding + Vector Search

Chunks are embedded using all-mpnet-base-v2 (768-dimensional vectors)
FAISS IndexFlatL2 performs similarity search to retrieve top 10 chunks
CrossEncoder ms-marco-MiniLM-L-6-v2 reranks results to top 5 by relevance

LLM Analysis

Google Gemini Flash Lite generates a structured multi-paragraph explanation
Response begins with the canonical concept name in "ConceptName: explanation" format
Runs in parallel with startup ecosystem lookup to reduce latency

Smart Caching (Hot / Warm / Cold Tiers)

Every concept is stored in SQLite with frequency, recency, and rediscovery metrics
A composite weight score determines the storage tier:
Hot: weight >= 80 (frequently and recently accessed)
Warm: weight >= 30 (moderately active)
Cold: weight < 30 (inactive for extended periods)
LRU demotion: Hot to Warm after 3 days without access; Warm to Cold after 14 days

Startup Ecosystem

Gemini also returns a list of real Global and Indian startups working in the searched concept's space
Results include company name and country

TECH STACK
Python 3.10+
FastAPI + Uvicorn
Google Gemini API (google-generativeai)
Sentence Transformers (all-mpnet-base-v2)
FAISS (faiss-cpu)
KeyBERT
SQLite (dual-database: auth.db + database.db + knowledge.db)
HTML + CSS + Vanilla JavaScript (no frontend framework)

PYTHON PACKAGES REQUIRED
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

ENVIRONMENT VARIABLES
Create a .env file in the project root:

GEMINI_API_KEY=your_gemini_api_key

Get your free Gemini API key at https://aistudio.google.com/apikey

RUNNING THE PROJECT
Start the server:

uvicorn redEngine.api.app:app --host 127.0.0.1 --port 8080 --reload

Open in browser:

http://127.0.0.1:8080

API USAGE
Authentication

POST /auth/signup
Content-Type: application/json
{ "username": "yourname", "email": "your@email.com", "password": "Pass@1234" }

POST /auth/login
Content-Type: application/json
{ "username": "yourname", "password": "Pass@1234" }

Analyze a Concept

POST /analyze
Authorization: Bearer YOUR_SESSION_TOKEN
Content-Type: application/json
{ "idea": "invention of zero" }

Response:

{
  "concept_name": "Zero",
  "analysis": "Zero: The concept of zero as a number originated...",
  "matches": [...],
  "resources": [...],
  "startups": [{ "name": "Wolfram Alpha", "country": "USA" }, ...]
}

Retrieve All Cached Concepts

GET /concepts
Authorization: Bearer YOUR_SESSION_TOKEN

FUTURE SCOPE
Multi-turn conversation memory per concept
Graph-based knowledge relationships between concepts
Detect duplicate ideas submitted by different users
Browser extension for one-click concept lookup
Export personal knowledge cache as PDF or Word
Multi-language concept support
