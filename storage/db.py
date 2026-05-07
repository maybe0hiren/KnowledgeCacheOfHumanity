import sqlite3
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


def _migrate():
    """Add any missing columns to existing tables without losing data."""
    conn = sqlite3.connect(str(dbPath))
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(concepts)").fetchall()}
        if "description" not in existing:
            conn.execute("ALTER TABLE concepts ADD COLUMN description TEXT NOT NULL DEFAULT ''")
            conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_migrate()