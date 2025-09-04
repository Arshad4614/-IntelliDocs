import os
import logging
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from groq import Groq

from backend.database.mongodb import db
from backend.utils.embedding_handler import get_query_embedding, get_embeddings
from backend.database.faiss_handler import (
    search_in_faiss_for_user,
    conv_search,
    conv_save_vectors,
)

# ---------------- Groq client ----------------
_CLIENT: Optional[Groq] = None
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

logger = logging.getLogger("chat_service")
logging.basicConfig(level=logging.INFO)


def _get_groq_client() -> Groq:
    global _CLIENT
    if _CLIENT is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set")
        _CLIENT = Groq(api_key=api_key)
    return _CLIENT


# ---------------- Indexes  mongo db opitimized index for queries----------------
def ensure_indexes(messages: Collection):
    messages.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    messages.create_index([("conversation_id", ASCENDING), ("created_at", ASCENDING)])
    messages.create_index([("conversation_id", ASCENDING), ("user_id", ASCENDING)])


# --------Save Message ---insert msg of every user or assitant to DB-----
def save_message(
    messages: Collection,
    *,
    user_id: str,
    role: str,
    content: str,
    conversation_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> dict:
    """
    Save a message into MongoDB.
    - Stores conversation_id both as ObjectId (for Mongo relations)
      and conversation_id_str (for FAISS + frontend consistency).
    """
    doc = {
        "conversation_id": str(conversation_id) if conversation_id else None,
        "conversation_id_str": str(conversation_id) if conversation_id else None,  # ✅ new field
        "user_id": str(user_id),
        "role": role,
        "content": content,
        "created_at": created_at or datetime.utcnow(),
        "deleted": False,
    }
    res = messages.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc

# ---------------- Main RAG Chat ----------------
def chat_with_rag(
    messages: Collection,
    user_id: str,
    query: str,
    conversation_id: Optional[str] = None,
    doc_id: Optional[str] = None,
) -> dict:
    start_time = datetime.utcnow()

    # Ensure conversation_id is string
    if conversation_id:
        conv_id_str = str(conversation_id)
    else:
        conv_id_str = str(db.conversations.insert_one({
            "user_id": str(user_id),
            "title": "New Chat",   # ✅ start with placeholder title
            "created_at": datetime.utcnow(),
            "deleted": False,
        }).inserted_id)

    # Save USER message
    user_msg = save_message(
        messages,
        user_id=str(user_id),
        role="user",
        content=query,
        conversation_id=conv_id_str,
    )

    # 🆕 Auto-update conversation title from first user message
    try:
        conv = db.conversations.find_one({"_id": ObjectId(conv_id_str)})
        if conv and (conv.get("title") in ["Untitled", "New Chat", None]):
            db.conversations.update_one(
                {"_id": ObjectId(conv_id_str)},
                {"$set": {"title": query[:50]}}   # ✅ title from first user message
            )
    except Exception as e:
        logger.warning(f"Failed to auto-update conversation title: {e}")

    # ---- Embedding
    qvec = get_query_embedding(query)

    # ---- Document retrieval
    doc_hits = search_in_faiss_for_user(
        query_vector=qvec,
        user_id=str(user_id),
        doc_id=str(doc_id) if doc_id else None,
        top_k=8,
    )
    doc_chunks = [h["text"] for h in doc_hits]

    # ---- Conversation memory retrieval
    conv_hits = conv_search(
        user_id=str(user_id),
        conversation_id=conv_id_str,
        query_vector=qvec,
        top_k=5,
    )
    conv_chunks = [h["text"] for h in conv_hits]

    # ---- Prompt build
    context_snippets = doc_chunks + conv_chunks
    joined_context = "\n\n---\n\n".join(context_snippets) if context_snippets else "N/A"

    if any(word in query.lower() for word in ["summary", "summarize", "title", "overview"]):
        prompt = (
            "You are a helpful assistant. "
            "Provide a concise and accurate summary or title based only on the given context. "
            "Do NOT repeat the question, and do NOT say things like 'Based on the context'. "
            "Just give the direct final answer.\n\n"
            f"Context:\n{joined_context}\n\n"
            f"Task: {query}\n\n"
            "Final Answer:"
        )
    else:
        prompt = (
            "You are a Retrieval-Augmented Generation (RAG) assistant. "
            "Always answer the user’s question using ONLY the provided context if relevant. "
            "If the context is not relevant, politely say so and then answer using your general knowledge. "
            "Do NOT repeat the question, and do NOT use phrases like 'Based on the provided context'. "
            "Just return the direct answer in a clean way.\n\n"
            f"Context:\n{joined_context}\n\n"
            f"Question: {query}\n\n"
            "Final Answer:"
        )

    # ---- LLM call
    try:
        client = _get_groq_client()
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are an AI assistant that follows instructions carefully."},
                {"role": "user", "content": prompt},
            ],
        )
        answer = completion.choices[0].message.content if completion.choices else ""
    except Exception as e:
        logger.error(f"Groq call failed: {e}")
        answer = "Sorry, I couldn't generate a response right now. Please try again."

    # Save ASSISTANT message
    asst_msg = save_message(
        messages,
        user_id=str(user_id),
        role="assistant",
        content=answer,
        conversation_id=conv_id_str,
    )

    # ---- Save embeddings for memory
    try:
        conv_save_vectors(
            user_id=str(user_id),
            conversation_id=conv_id_str,
            texts=[query, answer],
            vectors=get_embeddings([query, answer]),
            roles=["user", "assistant"],
            message_ids=[str(user_msg["_id"]), str(asst_msg["_id"])],
        )
    except Exception as e:
        logger.warning(f"Failed to save conv embeddings: {e}")

    # ---- Build sources
    sources = [
        {
            "filename": h["metadata"].get("filename"),
            "doc_id": str(h["metadata"].get("doc_id")),
            "snippet": h["text"][:200],
            "score": h.get("score"),
        }
        for h in doc_hits[:3]
    ]

    return {
        "answer": answer,
        "sources": sources,
        "conversation_id": conv_id_str,
        "doc_id": str(doc_id) if doc_id else None,
        "retrieval_count": len(doc_chunks),
        "processing_time": str(datetime.utcnow() - start_time),
    }

# ---------------- Get Conversation History ----------------
def get_conversation_history(messages: Collection, user_id: str, conversation_id: str) -> List[dict]:
    cid = str(conversation_id)
    items = list(
        messages.find({"conversation_id": cid, "user_id": str(user_id), "deleted": False}).sort("created_at", 1)
    )
    return [
        {"role": m["role"], "content": m["content"], "created_at": m["created_at"]}
        for m in items
    ]


# ---------------- List Conversations ----------------
def list_conversations(user_id: str) -> List[dict]:
    cur = db.conversations.find(
        {"user_id": str(user_id), "deleted": False}
    ).sort("created_at", -1)

    return [
        {
            "_id": str(c["_id"]),
            "title": c.get("title") or "Untitled",
            "created_at": c.get("created_at"),
        }
        for c in cur
    ]


# ---------------- Delete Conversation (soft delete) ----------------
def delete_conversation(user_id: str, conversation_id: str) -> dict:
    cid = str(conversation_id)
    db.conversations.update_one(
        {"_id": cid, "user_id": str(user_id)},
        {"$set": {"deleted": True}}
    )
    db.messages.update_many(
        {"conversation_id": cid, "user_id": str(user_id)},
        {"$set": {"deleted": True}}
    )
    return {"ok": True}
