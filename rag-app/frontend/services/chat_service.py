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
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

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


# ---------------- Indexes ----------------
def ensure_indexes(messages: Collection):
    messages.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    messages.create_index([("conversation_id", ASCENDING), ("created_at", ASCENDING)])
    messages.create_index([("conversation_id", ASCENDING), ("user_id", ASCENDING)])


# ---------------- Message helpers ----------------
def save_message(
    messages: Collection,
    *,
    user_id: str,
    role: str,
    content: str,
    conversation_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> dict:
    doc = {
        "conversation_id": ObjectId(conversation_id) if conversation_id else None,
        "user_id": str(user_id),
        "role": role,
        "content": content,
        "created_at": created_at or datetime.utcnow(),
        "deleted": False,
    }
    res = messages.insert_one(doc)
    doc["_id"] = res.inserted_id
    return doc


# ---------------- RAG chat ----------------
def chat_with_rag(
    messages: Collection,
    user_id: str,
    query: str,
    conversation_id: Optional[str] = None,
    doc_id: Optional[str] = None,
) -> dict:
    start_time = datetime.utcnow()

    # create or reuse conversation
    if conversation_id:
        conv_id = str(conversation_id)
    else:
        conv_oid = ObjectId()
        conv_id = str(conv_oid)
        db.conversations.insert_one({
            "_id": conv_oid,
            "user_id": str(user_id),
            "title": query[:80] if query else "New session",
            "created_at": datetime.utcnow(),
            "deleted": False,
        })

    # Save USER message
    user_msg = save_message(
        messages,
        user_id=str(user_id),
        role="user",
        content=query,
        conversation_id=conv_id,
    )

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
        conversation_id=str(conv_id),
        query_vector=qvec,
        top_k=5,
    )
    conv_chunks = [h["text"] for h in conv_hits]

    # ---- Prompt build
    context_snippets = doc_chunks + conv_chunks
    joined_context = "\n\n---\n\n".join(context_snippets) if context_snippets else "N/A"

    if any(word in query.lower() for word in ["summary", "summarize", "title", "overview"]):
        prompt = (
            "You are a helpful assistant. Based on the retrieved passages, "
            "provide a concise and accurate summary or title.\n\n"
            f"Context:\n{joined_context}\n\n"
            f"Task: {query}\n"
            "Answer:"
        )
    else:
        prompt = (
            "You are a precise RAG assistant.\n"
            "Use the provided context to answer.\n"
            "If the answer is not clearly present, give your best summary or inference from the context.\n"
            "If it is completely unrelated, reply: 'The answer is out of context.'\n\n"
            f"Context:\n{joined_context}\n\n"
            f"Question: {query}\n"
            "Answer:"
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
        conversation_id=conv_id,
    )

    # ---- Save embeddings for memory
    try:
        conv_save_vectors(
            user_id=str(user_id),
            conversation_id=str(conv_id),
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
        "conversation_id": conv_id,
        "doc_id": str(doc_id) if doc_id else None,
        "retrieval_count": len(doc_chunks),
        "processing_time": str(datetime.utcnow() - start_time),
    }


# ---------------- Conversation History ----------------
def get_conversation_history(messages: Collection, user_id: str, conversation_id: str) -> List[dict]:
    cid = ObjectId(conversation_id)
    items = list(
    messages.find({"conversation_id": str(conversation_id), "user_id": str(user_id), "deleted": False})
    .sort("created_at", 1)
)

    return [
        {"role": m["role"], "content": m["content"], "created_at": m["created_at"]}
        for m in items
    ]


# ---------------- Conversations List ----------------
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


# ---------------- Delete Conversation ----------------
def delete_conversation(user_id: str, conversation_id: str) -> dict:
    cid = ObjectId(conversation_id)
    db.conversations.update_one(
        {"_id": cid, "user_id": str(user_id)},
        {"$set": {"deleted": True}}
    )
    db.messages.update_many(
        {"conversation_id": cid, "user_id": str(user_id)},
        {"$set": {"deleted": True}}
    )
    return {"ok": True}
    if res.matched_count == 0:
        raise ValueError("Conversation not found")
    