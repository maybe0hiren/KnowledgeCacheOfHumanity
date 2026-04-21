from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Concept(Base):

    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    frequency = Column(Integer, default=1)
    rediscoveryCount = Column(Integer, default=0)
    weight = Column(Float, default=0)
    storageLayer = Column(String, default="warm")
    lastAccessed = Column(DateTime, default=datetime.utcnow)
    createdAt = Column(DateTime, default=datetime.utcnow)