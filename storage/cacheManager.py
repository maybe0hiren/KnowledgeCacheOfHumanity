from storage.db import SessionLocal
from storage.models import Concept
from storage.rankingManager import calculateWeight

def rearrangeLayers():

    db = SessionLocal()

    concepts = db.query(Concept).all()

    for concept in concepts:

        concept.weight = calculateWeight(concept)

        if concept.weight >= 80:
            concept.storageLayer = "hot"

        elif concept.weight >= 30:
            concept.storageLayer = "warm"

        else:
            concept.storageLayer = "cold"

    db.commit()
    db.close()