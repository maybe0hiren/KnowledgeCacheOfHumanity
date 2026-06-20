import hashlib
import re
import secrets
import random
import string
import sqlite3
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


def _migrate_auth_db():
    """Add must_change_password column if missing; existing users default to 1 (must change)."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "must_change_password" not in existing:
            conn.execute(
                "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 1"
            )
            conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_migrate_auth_db()


def _validate_password(password: str):
    """Returns error string if invalid, None if valid."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r'[0-9]', password):
        return "Password must contain at least 1 number."
    if not re.search(r'[^a-zA-Z0-9]', password):
        return "Password must contain at least 1 special character (e.g. !@#$%)."
    return None


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
    err = _validate_password(password)
    if err:
        return {"success": False, "error": err}
    db = _SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            return {"success": False, "error": "Username already taken"}
        if db.query(User).filter(User.email == email).first():
            return {"success": False, "error": "Email already registered"}
        user = User(
            username=username,
            email=email,
            password_hash=_hash_password(password),
            must_change_password=False,
        )
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
        return {
            "success": True,
            "token": token,
            "username": user.username,
            "must_change_password": bool(user.must_change_password),
        }
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
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "must_change_password": bool(user.must_change_password),
        }
    finally:
        db.close()


def logout(token: str) -> None:
    db = _SessionLocal()
    try:
        db.query(Session).filter(Session.token == token).delete()
        db.commit()
    finally:
        db.close()


def forgot_password(username: str) -> dict:
    """Generate a temporary password, set must_change_password=True, return temp password."""
    db = _SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return {"success": False, "error": "No account found with that username."}
        chars = string.ascii_letters + string.digits
        temp_password = (
            ''.join(random.choices(chars, k=8))
            + random.choice('!@#$%')
            + str(random.randint(10, 99))
        )
        user.password_hash = _hash_password(temp_password)
        user.must_change_password = True
        db.commit()
        return {"success": True, "temp_password": temp_password}
    finally:
        db.close()


def change_password(token: str, new_password: str) -> dict:
    """Validate new password, update hash, clear must_change_password flag."""
    err = _validate_password(new_password)
    if err:
        return {"success": False, "error": err}
    db = _SessionLocal()
    try:
        session = db.query(Session).filter(Session.token == token).first()
        if not session or session.expires_at < datetime.utcnow():
            return {"success": False, "error": "Session expired. Please log in again."}
        user = db.query(User).filter(User.id == session.user_id).first()
        if not user:
            return {"success": False, "error": "User not found."}
        user.password_hash = _hash_password(new_password)
        user.must_change_password = False
        db.commit()
        return {"success": True}
    finally:
        db.close()
