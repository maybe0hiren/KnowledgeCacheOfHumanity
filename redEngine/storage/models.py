from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Document(Base):

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    url = Column(String)
    title = Column(String)
    content = Column(Text)

class Concept(Base):

    __tablename__ = "concepts"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    rediscoveryCount = Column(Integer)