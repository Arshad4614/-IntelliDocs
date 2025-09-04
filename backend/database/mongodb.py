# backend/database/mongodb.py
from pymongo import MongoClient
from pymongo.database import Database
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB  = os.getenv("MONGO_DB", "user_db")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set in environment/.env")

# Single shared client
client = MongoClient(MONGO_URI)

# Typed Database object (helps remove yellow underlines in VS Code)
db: Database = client[MONGO_DB]

# Some legacy code may import `collection` directly:
collection = db["users"]

def get_db() -> Database:
    """Return the shared database object."""
    return db
sessions = db["sessions"]
# one-time at startup (or run once in REPL)
sessions.create_index([("user_id", 1), ("revoked", 1)])
sessions.create_index([("sid", 1)], unique=True)


