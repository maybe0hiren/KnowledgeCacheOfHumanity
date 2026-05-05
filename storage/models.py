from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class Concept(Base):
    __tablename__ = "concepts"

    id               = Column(Integer, primary_key=True)
    name             = Column(String, unique=True, nullable=False)
    frequency        = Column(Integer, default=1)
    rediscoveryCount = Column(Integer, default=0)
    weight           = Column(Float, default=0)
    storageLayer     = Column(String, default="warm")
    lastAccessed     = Column(DateTime, default=datetime.utcnow)
    createdAt        = Column(DateTime, default=datetime.utcnow)


class ConceptResource(Base):
    __tablename__ = "concept_resources"

    id            = Column(Integer, primary_key=True)
    concept_name  = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=False)
    title         = Column(String, default="")
    url           = Column(String, default="")
    added_at      = Column(DateTime, default=datetime.utcnow)