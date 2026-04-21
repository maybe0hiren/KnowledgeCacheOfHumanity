from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path

baseDir = Path(__file__).resolve().parent
dbPath = baseDir / "database.db"

engine = create_engine(f"sqlite:///{dbPath}", echo=False)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)