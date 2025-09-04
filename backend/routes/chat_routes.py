from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict
from bson import ObjectId
from backend.database.faiss_handler import _norm_id, search_in_faiss_for_user
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from backend.utils.jwt_handler import require_user
from backend.utils.embedding_handler import get_query_embedding
from backend.database.mongodb import db
from backend.services.chat_service import ensure_indexes, chat_with_rag

router = APIRouter(prefix="/chat", tags=["chat"])

messages = db["messages"]
conversations = db["conversations"]

# ---------------- Startup ----------------
@router.on_event("startup")
def _ensure_idx():
    ensure_indexes(messages)

# ---------------- Schema ----------------
class ChatBody(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    doc_id: Optional[str] = None

# ---------------- Chat ----------------
@router.post("/send")
async def chat_send(body: ChatBody, user=Depends(require_user)):
    """
    Send a chat message with RAG support + fallback to chat_with_rag.
    """
    q = (body.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question is required")

    try:
        # --- Step 1: FAISS retrieval ---
        hits = []
        if body.doc_id:
            qvec = get_query_embedding(q)
            hits = search_in_faiss_for_user(
                query_vector=qvec,
                user_id=str(user["_id"]),
                doc_id=body.doc_id,
                top_k=5
            )

        if not hits:
            context = "⚠️ No relevant document context found."
        else:
            context = "\n\n".join([h["text"] for h in hits])

        # --- Step 2: Groq API ---
       # try:
        #    answer = (q, context)
        #except Exception as e:
            # Graceful failure → still continue with fallback
         #   return {
          #      "question": q,
           #     "answer": f"⚠️ Chat service error: {e}",
            #    "context": context,
            #}

        # --- Step 3: Save conversation ---
        conv_id = body.conversation_id or str(
            db.conversations.insert_one({
                "user_id": str(user["_id"]),
                "created_at": datetime.utcnow(),
                "deleted": False
            }).inserted_id
        )

        db.messages.insert_one({
            "conversation_id": conv_id,
            "user_id": str(user["_id"]),
            "role": "user",
            "content": q,
            "created_at": datetime.utcnow(),
            "doc_id": body.doc_id,
            "deleted": False
        })
        db.messages.insert_one({
            "conversation_id": conv_id,
            "user_id": str(user["_id"]),
            "role": "assistant",
            "content": answer, # type: ignore
            "created_at": datetime.utcnow(),
            "doc_id": body.doc_id,
            "deleted": False
        })

        return {
            "question": q,
            "answer": answer, # type: ignore
            "context": context,
            "conversation_id": conv_id,
        }

    except Exception as e:
        # 🔄 Fallback to chat_with_rag if new pipeline fails
        try:
            out = chat_with_rag(
                messages,
                user_id=_norm_id(user["_id"]),   # always string
                query=q,
                conversation_id=_norm_id(body.conversation_id) if body.conversation_id else None,
                doc_id=_norm_id(body.doc_id) if body.doc_id else None
            )
            return out
        except Exception as inner:
            raise HTTPException(status_code=500, detail=f"Chat failed (both pipelines): {inner}")

# ---------------- All History Return user chat msges it is hit when we call history fron frontend (messages) ----------------
@router.get("/history")
def get_history(user=Depends(require_user)):
    if "_id" not in user:
        raise HTTPException(400, "User data is missing _id field")

    try:
        convs = conversations.find(
            {"user_id": str(user["_id"]), "deleted": False}
        ).sort("created_at", -1)

        output = []
        for conv in convs:
            msgs = list(messages.find(
                {"conversation_id": str(conv["_id"]), "user_id": str(user["_id"]), "deleted": False}
            ).sort("created_at", 1))

            output.append({
                "conversation_id": str(conv["_id"]),
                "title": conv.get("title") or "New Session",
                "created_at": conv.get("created_at"),
                "messages": [
                    {"role": m["role"], "content": m["content"], "created_at": m["created_at"]}
                    for m in msgs
                ]
            })

        return {"conversations": output}
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch history: {e}")


# -- One Conversation ----when user open its old chat that  point hit this route and get the old history ---------
@router.get("/history/{conversation_id}")
def get_history_conversation(conversation_id: str, user=Depends(require_user)):
    if "_id" not in user:
        raise HTTPException(400, "User data is missing _id field")

    # ✅ Convert conversation_id to ObjectId
    try:
        cid = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(400, "Invalid conversation_id")

    # ✅ Find conversation
    conv = conversations.find_one({"_id": cid, "user_id": str(user["_id"])})
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # ✅ Get all messages in that conversation
    items = list(
        messages.find({"conversation_id": str(cid), "user_id": str(user["_id"])}).sort("created_at", 1)
    )

    out = [
        {"_id": str(m["_id"]), "role": m.get("role"), "content": m.get("content")}
        for m in items
    ]

    return {
        "conversation_id": str(conv["_id"]),   # always return string to frontend
        "title": conv.get("title") or "Conversation",
        "messages": out,
    }


# -- Conversations List ----front end side bar to get specific collection ---#
@router.get("/conversations")
def list_conversations(user=Depends(require_user)):
    if "_id" not in user:
        raise HTTPException(400, "User data is missing _id field")
    try:
        cur = conversations.find(
            {"user_id": str(user["_id"]), "deleted": False}
        ).sort("created_at", -1)

        return {
            "conversations": [
                {
                    "conversation_id": str(c["_id"]),
                    "title": c.get("title") or "Conversation",
                    "created_at": c.get("created_at"),
                }
                for c in cur
            ]
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch conversations: {e}")


# ------Delete One Message ----when we delet only one msg from chat ----------
@router.delete("/history/item/{message_id}")
def delete_history_item(message_id: str, user=Depends(require_user)):
    if "_id" not in user:
        raise HTTPException(400, "User data is missing _id field")
    try:
        mid = ObjectId(message_id)
    except Exception:
        raise HTTPException(400, "Invalid message_id")

    res = messages.delete_one({"_id": mid, "user_id": str(user["_id"])})
    if res.deleted_count == 0:
        raise HTTPException(404, "Message not found")
    return {"ok": True, "deleted": 1}

# ---------------- Delete Whole Conversation ----------------
@router.delete("/history/conversation")
def delete_history_conversation(conversation_id: str = Query(...), user=Depends(require_user)):
    if "_id" not in user:
        raise HTTPException(400, "User data is missing _id field")
    try:
        cid = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(400, "Invalid conversation_id")

    conv = conversations.find_one({"_id": cid, "user_id": str(user["_id"])})
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # 🔄 Soft delete instead of removing permanently
    res = messages.update_many(
        {"conversation_id": str(cid), "user_id": str(user["_id"])},
        {"$set": {"deleted": True}}
    )
    conversations.update_one(
        {"_id": cid, "user_id": str(user["_id"])},
        {"$set": {"deleted": True}}
    )

    return {"ok": True, "deleted_messages": int(res.modified_count)}
