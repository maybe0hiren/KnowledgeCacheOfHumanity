from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from redEngine.services.rediscoveryService import processIdea
from search_response_registry.registry_manager import RegistryManager
from storage.dbManager import getConceptWithResources, getAllConcepts
from storage.db import engine
from storage.models import Base
from auth.routes import router as auth_router
from auth.auth_manager import get_user_from_token

_ROOT = Path(__file__).resolve().parents[2]
_KNOWLEDGE_DB = str(_ROOT / "storage" / "knowledge.db")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="KnowledgeCacheOfHumanity", lifespan=lifespan)

registry = RegistryManager(db_path=_KNOWLEDGE_DB)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


def _get_current_user(request: Request) -> dict | None:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else request.cookies.get("session_token")
    if not token:
        return None
    return get_user_from_token(token)


class IdeaRequest(BaseModel):
    idea: str


@app.post("/analyze")
async def analyzeIdea(request: Request, body: IdeaRequest):
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Login required"})
    try:
        result = await processIdea(body.idea, registry)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": "Analysis failed", "detail": str(e)})
    print(f"[ANALYZE] Returning: analysis={bool(result.get('analysis'))}, "
          f"matches={len(result.get('matches', []))}, "
          f"resources={len(result.get('resources', []))}")
    return result


@app.get("/concept/{name}")
async def getConcept(name: str, request: Request):
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Login required"})
    data = getConceptWithResources(name)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Concept not found"})
    return data


@app.get("/concepts")
async def listConcepts(request: Request):
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Login required"})
    concepts = getAllConcepts()
    return [
        {
            "name":          c.name,
            "search_count":  c.frequency,
            "storage_layer": c.storageLayer,
            "last_accessed": c.lastAccessed.isoformat(),
        }
        for c in concepts
    ]


@app.get("/registry/stats")
async def registryStats(request: Request):
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"error": "Login required"})
    return registry.registry_stats()