# models/chat_model.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ChatMessageIn(BaseModel):
    conversation_id: Optional[str] = None
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str

class ChatMessageOut(BaseModel):
    id: str
    conversation_id: Optional[str] = None
    user_id: str
    role: str
    content: str
    created_at: datetime

class ChatHistoryResponse(BaseModel):
    items: List[ChatMessageOut]
    next_cursor: Optional[str] = None

# chat_model.py
class DeleteResponse(BaseModel):
    deleted: int
