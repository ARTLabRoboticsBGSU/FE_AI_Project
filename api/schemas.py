from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class ChatMessage(BaseModel):
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    messages: List[ChatMessage]
    model: Optional[str] = None
    stream: Optional[bool] = False

class ChatResponse(BaseModel):
    message_id: str
    content: str
    model_used: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None

class ChatSessionCreate(BaseModel):
    user_id: Optional[str] = None
    context: Optional[str] = None
    ttl_seconds: Optional[int] = 86400

class ChatHistoryItem(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    created_at: datetime
    model_used: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None

class ClassifyRequest(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None

class ClassifyResponse(BaseModel):
    labels: List[Dict[str, Any]]

class XAPIEvent(BaseModel):
    actor: Dict[str, Any]
    verb: Dict[str, Any]
    object: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None

class AnalyticsSummaryResponse(BaseModel):
    total_sessions: int
    total_messages: int
    active_users: int
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

class StudentEngagementResponse(BaseModel):
    student_id: str
    interactions: int
    last_active: Optional[datetime] = None
    time_spent_seconds: Optional[int] = None

class TopicDifficultyResponse(BaseModel):
    topic: str
    difficulty_score: float
    samples: Optional[List[str]] = None
