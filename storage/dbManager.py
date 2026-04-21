from storage.db import SessionLocal
from storage.models import Concept
from datetime import datetime

def saveOrUpdateConcept(name):

    db = SessionLocal()

    concept = db.query(Concept).filter(
        Concept.name == name
    ).first()

    if concept:

        concept.frequency += 1
        concept.lastAccessed = datetime.utcnow()

    else:

        concept = Concept(name=name)
        db.add(concept)

    db.commit()
    db.close()

def getAllConcepts():

    db = SessionLocal()

    data = db.query(Concept).all()

    db.close()

    return data