"""
Chat + Embedding Service

This module handles:
- Fetching old conversations from MongoDB
- Retrieving embeddings for conversation messages
- Using FAISS to get semantic search context
- Calling LLM for response generation
"""

from fastapi import HTTPException
from backend.database.faiss_handler import search_in_faiss_for_user, conv_search
from backend.services.llm_services import call_llm
from backend.database.mongodb import db
from bson import ObjectId
from sentence_transformers import SentenceTransformer


# -----------------------------
# Load embedding model once
# -----------------------------
_model = SentenceTransformer("all-MiniLM-L6-v2")


def get_query_embedding(text: str) -> list[float]:
    """
    Generate an embedding for a single text string.
    Returns a list of floats (vector).
    """
    if not text or not text.strip():
        return []
    embedding = _model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts.
    Returns a list of float lists (matrix).
    """
    if not texts:
        return []
    embeddings = _model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


# -----------------------------
# Conversation logic
# -----------------------------
def get_conversation_history(user_id: str, conversation_id: str):
    """
    Fetch the entire conversation history for the given conversation_id.
    If the document is deleted, still retrieve the conversation context from FAISS.
    """
    conversation = db.conversations.find_one(
        {"_id": ObjectId(conversation_id), "user_id": user_id}
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Retrieve all messages in the conversation, even if document is deleted
    items = list(
        db.messages.find({"conversation_id": ObjectId(conversation_id), "user_id": user_id})
        .sort("created_at", 1)
    )

    # Extract text and prepare embeddings
    conversation_context = [{"role": m["role"], "content": m["content"]} for m in items]

    embeddings = []
    for item in conversation_context:
        try:
            query_vector = get_query_embedding(item["content"])  # Create the query embedding
            result = search_in_faiss_for_user(query_vector, user_id=user_id)
            embeddings.append(result)
        except Exception as e:
            embeddings.append({"error": f"Embedding failed for: {item['content'][:50]} | {str(e)}"})

    return conversation_context, embeddings


def chat_with_old_conversation(messages, user_id: str, query: str, conversation_id: str):
    """
    Query a conversation, even if documents have been deleted, using the embeddings in FAISS.
    """
    try:
        conversation_history, embeddings = get_conversation_history(user_id, conversation_id)
        
        # Use retrieved context and embeddings for query answering
        response = process_query_with_context(query, conversation_history, embeddings)
        
        return response
    except Exception as e:
        return {"error": str(e)}


def process_query_with_context(query, conversation_history, embeddings):
    """
    Process the query with the conversation context and embeddings.
    Uses an LLM to answer.
    """
    # Combine conversation history and embeddings context to form a prompt for LLM
    context = "\n".join([f"{m['role']}: {m['content']}" for m in conversation_history])
    
    # Optionally add embedding info (if useful for the LLM)
    emb_context = "\n".join([str(e) for e in embeddings if isinstance(e, dict) or isinstance(e, str)])

    prompt = (
        f"Conversation History:\n{context}\n\n"
        f"Embedding Context:\n{emb_context}\n\n"
        f"Question: {query}\nAnswer:"
    )
    
    # Call your LLM model
    answer = call_llm(prompt)
    
    return {"answer": answer}
