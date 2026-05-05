# redEngine/api/app.py  (after change)
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from redEngine.services.rediscoveryService import processIdea
from MOM.mom_manager import MOMManager          # ← add

app = FastAPI()

mom = MOMManager(db_path="storage/knowledge.db") # ← add (singleton)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IdeaRequest(BaseModel):
    idea: str

@app.post("/analyze")
async def analyzeIdea(request: IdeaRequest):
    result = await processIdea(request.idea, mom)  # ← pass mom in
    return result