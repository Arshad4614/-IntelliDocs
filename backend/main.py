from dotenv import load_dotenv
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging

# ---------- Load environment variables ----------
load_dotenv()  # loads .env from the working directory

# Logging setup
logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO)

# Quick sanity check for the Groq API Key
groq_key = os.getenv("GROQ_API_KEY")
if groq_key:
    logger.info("GROQ_API_KEY loaded successfully.")
else:
    logger.error("GROQ_API_KEY is missing. Check your .env file and working directory.")
    raise HTTPException(status_code=500, detail="GROQ_API_KEY is missing")

# ---------- Database client (placeholder) ----------
# Replace this with your actual database client/connection, e.g., SQLAlchemy session or Motor client.
db = None

# ---------- Initialize FastAPI ----------
app = FastAPI(title="RAG API", version="1.0.0")

# Enable CORS (allow all origins for now — tighten for production) middleware CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update to specific origins for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Routers ----------
# Import the routers that actually exist
from backend.routes.user_routes import router as user_router
from backend.routes.chat_routes import router as chat_router
from backend.routes.doc_routes import router as doc_router
from backend.routes.session_routes import router as session_router

# ---------- Register routers ----------
app.include_router(user_router, prefix="/users", tags=["Users"])
app.include_router(chat_router)                      # /chat...
app.include_router(doc_router)                       # /docs...
app.include_router(session_router)                   # /sessions...

# ---------- Root health check ----------
@app.get("/")
def root():
    logger.info("Health check successful")
    return {"message": "RAG API is running"}

# ---------- Enhanced Health Check ----------
@app.get("/health")
def health_check():
    # Add additional checks (database, external services, etc.)
    # For example: Check if the database is connected and whether any external APIs are available.
    try:
        # Assuming db is connected if this line runs
        db_status = "connected" if db else "not connected"
        return {"status": "OK", "database": db_status, "external_service": "online"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")

