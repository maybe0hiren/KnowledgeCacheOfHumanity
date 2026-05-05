from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

AuthBase = declarative_base()


class User(AuthBase):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True)
    username      = Column(String, unique=True, nullable=False)
    email         = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)


class Session(AuthBase):
    __tablename__ = "sessions"

    id         = Column(Integer, primary_key=True)
    token      = Column(String, unique=True, nullable=False)
    user_id    = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)