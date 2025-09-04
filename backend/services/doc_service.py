from datetime import datetime
import os
from typing import Dict, Any
from bson import ObjectId
from langchain_community.document_loaders import PyPDFLoader, TextLoader
import hashlib

try:
    import docx2txt
    HAS_DOCX = True
except Exception:
    HAS_DOCX = False

from backend.utils.chunkers import chunk_text
from backend.utils.embedding_handler import get_embeddings
from backend.database.faiss_handler import save_to_faiss
from backend.database.mongodb import db
from backend.database.faiss_handler import docs_remove_by_doc_id

#--this is file loader function--#
def _load_text(file_path: str, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        docs = PyPDFLoader(file_path).load()
        return "\n".join([d.page_content for d in docs])
    if lower.endswith(".txt"):
        docs = TextLoader(file_path, encoding="utf-8").load()
        return "\n".join([d.page_content for d in docs])
    if lower.endswith(".docx"):
        if not HAS_DOCX:
            raise RuntimeError("DOCX requires docx2txt, install via pip install docx2txt")
        return docx2txt.process(file_path)
    raise ValueError("Unsupported file type (PDF, TXT, DOCX allowed)")

#----it is the main point which is called after uploading a document---#
def process_document(file_path: str, filename: str, user_id: str) -> Dict[str, Any]:
    """
    Load, chunk, embed, and store a document in Mongo + FAISS.
    Returns: {"document_id": str, "chunk_count": int}
    """
    from backend.database.faiss_handler import save_to_faiss, docs_remove_by_doc_id, _norm_id

    user_id = str(user_id)   # normalize

    # ---- Load text
    text = _load_text(file_path, filename)
    if not text.strip():
        raise ValueError("Empty file")

    # ---- Chunk text
    chunks = chunk_text(text, chunk_size=1000, overlap=200)
    if not chunks:
        raise ValueError("No chunks created")

    # ---- Embeddings
    vectors = get_embeddings(chunks)

    # ---- Compute content hash
    h = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    content_hash = h.hexdigest()

    # ---- Check for existing document with same hash
    existing = db.documents.find_one({"user_id": user_id, "content_hash": content_hash})
    if existing:
        # Reuse existing doc
        doc_objid = existing["_id"]
        doc_id = str(doc_objid)

        rec = {
            "user_id": user_id,
            "filename": filename,
            "chunk_count": len(chunks),
            "size_bytes": os.path.getsize(file_path) if os.path.exists(file_path) else None,
            "created_at": datetime.utcnow(),
            "deleted": False,
            "content_hash": content_hash,
        }
        db.documents.update_one({"_id": doc_objid}, {"$set": rec}, upsert=True)

        # 🟢 delete old vectors only in existing doc case
        try:
            docs_remove_by_doc_id(user_id=_norm_id(user_id), doc_id=_norm_id(doc_id))
        except Exception as e:
            print("⚠️ FAISS delete failed:", e)
    else:
        # New doc
        doc_objid = ObjectId()
        doc_id = str(doc_objid)

        rec = {
            "_id": doc_objid,
            "user_id": user_id,
            "filename": filename,
            "chunk_count": len(chunks),
            "size_bytes": os.path.getsize(file_path) if os.path.exists(file_path) else None,
            "created_at": datetime.utcnow(),
            "deleted": False,
            "content_hash": content_hash,
        }
        db.documents.update_one({"_id": rec["_id"]}, {"$set": rec}, upsert=True)
        # ❌ no delete for new doc

    # ---- Save new vectors (force normalized IDs)
    metadata_list = [
        {
            "user_id": _norm_id(user_id),
            "doc_id": _norm_id(doc_id),
            "filename": filename,
            "chunk": c
        }
        for c in chunks
    ]
    save_to_faiss(vectors, metadata_list)

    print(f"✅ Saved {len(chunks)} chunks for doc_id={doc_id}")
    return {"document_id": doc_id, "chunk_count": len(chunks)}
