from storage.db import SessionLocal
from storage.models import Concept, ConceptResource
from datetime import datetime


def saveOrUpdateConcept(name: str, description: str = "", analysis: str = "") -> None:
    """
    name        — extracted concept name from LLM (e.g. "Photosynthesis")
    description — original user input (e.g. "Process by which plants make food")
    analysis    — LLM-generated explanation text (cached; only saved on first search)
    """
    db = SessionLocal()
    try:
        concept = db.query(Concept).filter(Concept.name == name).first()

        if concept:
            concept.frequency += 1
            concept.lastAccessed = datetime.utcnow()
            if description and not concept.description:
                concept.description = description
            # Only store analysis if not already cached
            if analysis and not concept.analysis:
                concept.analysis = analysis
        else:
            concept = Concept(
                name=name,
                description=description,
                analysis=analysis or None,
            )
            db.add(concept)

        db.commit()
    finally:
        db.close()


def getCachedAnalysis(idea: str) -> str | None:
    """
    Return the stored analysis for a given user query, or None if not cached.
    Matches on the original user input (description) or concept name (case-insensitive).
    """
    from sqlalchemy import func
    db = SessionLocal()
    try:
        concept = db.query(Concept).filter(
            (Concept.description == idea) |
            (func.lower(Concept.name) == idea.lower())
        ).filter(Concept.analysis.isnot(None)).first()
        return concept.analysis if concept else None
    finally:
        db.close()


def saveConceptResources(concept_name: str, resources: list) -> None:
    db = SessionLocal()
    try:
        for r in resources:
            url = r.get("url", "").strip()
            if not url:
                continue
            exists = db.query(ConceptResource).filter(
                ConceptResource.concept_name == concept_name,
                ConceptResource.url == url
            ).first()
            if not exists:
                db.add(ConceptResource(
                    concept_name=concept_name,
                    resource_type=r.get("resource_type", "unknown"),
                    title=r.get("title", ""),
                    url=url,
                ))
        db.commit()
    finally:
        db.close()


def getConceptWithResources(name: str) -> dict | None:
    db = SessionLocal()
    try:
        concept = db.query(Concept).filter(Concept.name == name).first()
        if not concept:
            return None
        resources = db.query(ConceptResource).filter(ConceptResource.concept_name == name).all()
        return {
            "concept":       concept.name,
            "description":   concept.description or "",
            "search_count":  concept.frequency,
            "storage_layer": concept.storageLayer,
            "last_accessed": concept.lastAccessed.isoformat(),
            "created_at":    concept.createdAt.isoformat(),
            "resources": [
                {"type": r.resource_type, "title": r.title, "url": r.url, "added_at": r.added_at.isoformat()}
                for r in resources
            ],
        }
    finally:
        db.close()


def getAllConcepts() -> list:
    db = SessionLocal()
    try:
        return db.query(Concept).order_by(Concept.frequency.desc()).all()
    finally:
        db.close()