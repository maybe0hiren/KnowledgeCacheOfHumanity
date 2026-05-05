from storage.db import engine
from storage.models import Base

Base.metadata.create_all(bind=engine)
print("Main database created (concepts, concept_resources)")

from auth.auth_manager import _engine as auth_engine
from auth.models import AuthBase

AuthBase.metadata.create_all(bind=auth_engine)
print("Auth database created (users, sessions)")