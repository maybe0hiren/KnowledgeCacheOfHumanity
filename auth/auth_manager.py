import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.models import AuthBase, User, Session

DB_PATH = Path(__file__).resolve().parent.parent / "storage" / "auth.db"
_engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
AuthBase.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)

SESSION_DURATION_HOURS = 24


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, hashed = stored.split(":", 1)
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == hashed
    except ValueError:
        return False


def signup(username: str, email: str, password: str) -> dict:
    db = _SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            return {"success": False, "error": "Username already taken"}
        if db.query(User).filter(User.email == email).first():
            return {"success": False, "error": "Email already registered"}
        user = User(username=username, email=email, password_hash=_hash_password(password))
        db.add(user)
        db.commit()
        return {"success": True}
    finally:
        db.close()


def login(username: str, password: str) -> dict:
    db = _SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not _verify_password(password, user.password_hash):
            return {"success": False, "error": "Invalid username or password"}
        token = secrets.token_hex(32)
        expires = datetime.utcnow() + timedelta(hours=SESSION_DURATION_HOURS)
        db.add(Session(token=token, user_id=user.id, expires_at=expires))
        db.commit()
        return {"success": True, "token": token, "username": user.username}
    finally:
        db.close()


def get_user_from_token(token: str) -> dict | None:
    db = _SessionLocal()
    try:
        session = db.query(Session).filter(Session.token == token).first()
        if not session or session.expires_at < datetime.utcnow():
            return None
        user = db.query(User).filter(User.id == session.user_id).first()
        if not user:
            return None
        return {"id": user.id, "username": user.username, "email": user.email}
    finally:
        db.close()


def logout(token: str) -> None:
    db = _SessionLocal()
    try:
        db.query(Session).filter(Session.token == token).delete()
        db.commit()
    finally:
        db.close()