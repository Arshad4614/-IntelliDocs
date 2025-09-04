# backend/routes/doc_routes.py
import os
import uuid
import shutil
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from backend.database.faiss_handler import docs_remove_by_doc_id, _norm_id
from bson import ObjectId
from backend.utils.jwt_handler import require_user
from backend.database.mongodb import db
from backend.services.doc_service import process_document

# Router
router = APIRouter(prefix="/docs", tags=["docs"])

# Config
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_UPLOAD_MB = 15
ALLOWED_EXTS = {".pdf", ".txt", ".docx"}

logger = logging.getLogger("docs_routes")
logging.basicConfig(level=logging.INFO)


# ---------------- Helpers ----------------
def _normalize_uid_str(user: dict) -> str:
    """Always return user_id as string."""
    return str(user.get("_id") or user.get("user_id"))


# --- Routes - when user upload document from frontend this endpoint is called -----------
@router.post("/upload")
async def upload_doc(file: UploadFile = File(...), user: dict = Depends(require_user)):
    """Upload and process a document."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Only {', '.join(sorted(ALLOWED_EXTS))} supported.")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(413, f"File too large ({size_mb:.1f} MB). Max {MAX_UPLOAD_MB}.")
    await file.seek(0)

    uid = _normalize_uid_str(user)
    tmp_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")

    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Process doc (chunks + embed + save Mongo + FAISS)
        result = process_document(tmp_path, file.filename, uid)

        return {
            "ok": True,
            **result,
            "filename": file.filename,
            "size_mb": round(size_mb, 2),
        }

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(500, f"Upload failed: {e}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

#--- when user open document page in frontend this endpoint is called ---------#
@router.get("/list")
async def list_docs(user: dict = Depends(require_user)):
    """List all documents for the current user."""
    uid = _normalize_uid_str(user)
    cur = db.documents.find({"user_id": uid, "deleted": False}).sort("created_at", -1)
    out = []
    for d in cur:
        out.append(
            {
                "_id": str(d["_id"]),
                "filename": d.get("filename"),
                "chunk_count": d.get("chunk_count"),
                "size_bytes": d.get("size_bytes"),
                "created_at": d.get("created_at"),
            }
        )
    return {"documents": out}

#-- when user delet a specific document in front end then this api is called---3#
@router.delete("/delete/{doc_id}")
async def delete_doc(doc_id: str, user: dict = Depends(require_user)):
    """Mark a document as deleted."""
    uid = _normalize_uid_str(user)
    try:
        oid = ObjectId(doc_id)
    except Exception:
        raise HTTPException(400, "Invalid document id")

    res = db.documents.update_one(
        {"_id": oid, "user_id": uid}, {"$set": {"deleted": True}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Document not found")
    docs_remove_by_doc_id(user_id=_norm_id(uid), doc_id=_norm_id(doc_id))
    return {"ok": True}
#-- when user click on clear all   in frontend then on the backend this endpoint is called ----#
@router.delete("/clear")
async def clear_docs(user: dict = Depends(require_user)):
    """Mark all documents as deleted for the current user."""
    uid = _normalize_uid_str(user)
    res = db.documents.update_many({"user_id": uid}, {"$set": {"deleted": True}})
    for d in db.documents.find({"user_id": uid}):
        docs_remove_by_doc_id(user_id=_norm_id(uid), doc_id=_norm_id(d["_id"]))
    return {"ok": True, "deleted": res.modified_count}
    
