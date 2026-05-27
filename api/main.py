from fastapi import FastAPI, HTTPException, Body, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional
from uuid import uuid4
from datetime import datetime

from api.schemas import (
    ChatRequest, ChatResponse, ChatSessionCreate, ChatHistoryItem,
    ClassifyRequest, ClassifyResponse, XAPIEvent, AnalyticsSummaryResponse,
    StudentEngagementResponse, TopicDifficultyResponse
)
from config import DEFAULT_MODELS
from lib.chatgeneration import generate_chat_completion
try:
    from lib.rag import RAGRetriever
except Exception:
    RAGRetriever = None

# Analytics agent (runs asynchronously)
try:
    from lib import analytics_agent
except Exception:
    analytics_agent = None

app = FastAPI(title="ChatISA API", version="0.1")

# In-memory stores for scaffolding/demo only
SESSIONS = {}
HISTORY = []

# ---------- Chat Interaction ----------
@app.post('/chat', response_model=ChatResponse)
def post_chat(req: ChatRequest, background_tasks: BackgroundTasks):
    """Accepts chat messages and returns a generated assistant reply (scaffold).

    In production, this should enqueue/model-invoke and stream if requested.
    """
    session_id = req.session_id or str(uuid4())
    # Determine model to use (caller-specified or page default)
    model_key = req.model or DEFAULT_MODELS.get('coding_companion')

    # Prepare messages for model
    messages_for_model = [{"role": m.role, "content": m.content} for m in req.messages]

    # Attempt RAG retrieval and inject as system message when available
    sources = []
    try:
        if RAGRetriever is not None:
            retr = RAGRetriever()
            docs = retr.retrieve(messages_for_model[-1]['content'] if messages_for_model else '', k=3)
            if docs:
                snippets = []
                for d in docs:
                    if isinstance(d, dict):
                        text = d.get('text','').strip()
                        src = d.get('source')
                    else:
                        text = getattr(d, 'page_content', str(d)).strip()
                        src = getattr(d, 'metadata', {}).get('source') if hasattr(d, 'metadata') else None
                    if text:
                        snippets.append(text[:1000])
                    if src:
                        sources.append({'source': src})
                if snippets:
                    rag_msg = {"role": "system", "content": "Relevant materials:\n\n" + "\n\n---\n\n".join(snippets)}
                    messages_for_model.insert(0, rag_msg)
    except Exception:
        sources = []

    # Call centralized chat generation util
    try:
        response_text, in_toks, out_toks = generate_chat_completion(model_key, messages_for_model, temp=0, max_num_tokens=1000)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {e}")

    msg_id = str(uuid4())
    HISTORY.append(ChatHistoryItem(
        message_id=msg_id,
        session_id=session_id,
        role='assistant',
        content=response_text,
        created_at=datetime.utcnow(),
        model_used=model_key,
        sources=sources
    ))

    # Trigger analytics asynchronously (do not block chat response)
    try:
        if analytics_agent is not None:
            # Build messages for analytics: include original user messages and assistant reply
            analytics_msgs = [
                {"role": m.role, "content": m.content} for m in req.messages
            ]
            analytics_msgs.append({"role": "assistant", "content": response_text})
            background_tasks.add_task(analytics_agent.process_interaction, session_id, analytics_msgs, model_key)
    except Exception:
        # Ignore analytics scheduling failures (do not break chat)
        pass

    return ChatResponse(message_id=msg_id, content=response_text, model_used=model_key, sources=sources)


@app.get('/chat/history', response_model=List[ChatHistoryItem])
def get_chat_history(session_id: Optional[str] = Query(None), page: int = 1, size: int = 50):
    """Return chat messages for a session (paginated)."""
    items = [h for h in HISTORY if (session_id is None or h.session_id == session_id)]
    start = (page - 1) * size
    return items[start:start+size]


@app.post('/chat/session')
def create_chat_session(req: ChatSessionCreate):
    sid = str(uuid4())
    SESSIONS[sid] = {
        'user_id': req.user_id,
        'context': req.context,
        'created_at': datetime.utcnow().isoformat(),
        'ttl_seconds': req.ttl_seconds
    }
    return JSONResponse(status_code=201, content={'session_id': sid})


# ---------- Analytics Processing ----------
@app.post('/classify', response_model=ClassifyResponse)
def post_classify(req: ClassifyRequest):
    # Use scaffolding classifier if available
    try:
        from lib import scaffolding_classifier
        # Build minimal messages payload from the content
        messages = [
            {"role": "user", "content": req.content}
        ]
        result = scaffolding_classifier.classify_interaction(messages)
        labels = [{"label": result.get('category'), "confidence": result.get('confidence'), "rationale": result.get('rationale')}]
        return ClassifyResponse(labels=labels)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {e}")


@app.post('/xapi-event')
def post_xapi_event(event: XAPIEvent):
    # In production, validate and enqueue for analytics processing
    return JSONResponse(status_code=202, content={'accepted': True})


# ---------- Instructor Analytics ----------
@app.get('/analytics-summary', response_model=AnalyticsSummaryResponse)
def get_analytics_summary(start: Optional[str] = None, end: Optional[str] = None):
    return AnalyticsSummaryResponse(total_sessions=len(SESSIONS), total_messages=len(HISTORY), active_users=1)


@app.get('/student-engagement', response_model=List[StudentEngagementResponse])
def get_student_engagement(limit: int = 100):
    # Return stubbed list
    return [StudentEngagementResponse(student_id='student-1', interactions=10, last_active=datetime.utcnow(), time_spent_seconds=3600)]


@app.get('/topic-difficulty', response_model=List[TopicDifficultyResponse])
def get_topic_difficulty(limit: int = 20):
    return [TopicDifficultyResponse(topic='PID tuning', difficulty_score=0.7, samples=['sample_doc.txt'])]


# Healthcheck
@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/analytics/aggregated')
def get_aggregated_analytics():
    """Return aggregated distributions for Bloom levels and scaffolding categories.

    Reads the activity log and aggregates entries with activity_type == 'analytics_classification'.
    """
    try:
        from lib import enhanced_usage_logger as elogger
    except Exception:
        raise HTTPException(status_code=500, detail="enhanced_usage_logger not available")

    try:
        entries = elogger.load_json_log(elogger.ACTIVITY_LOG_FILE)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read activity log: {e}")

    bloom_counts: dict = {}
    scaff_counts: dict = {}
    total = 0

    for entry in entries:
        try:
            if entry.get('activity_type') != 'analytics_classification':
                continue
            total += 1
            data = entry.get('data', {})
            bloom = data.get('bloom', {})
            scaff = data.get('scaffolding', {})

            level = (bloom.get('level') or 'Unknown')
            cat = (scaff.get('category') or 'Unknown')

            bloom_counts[level] = bloom_counts.get(level, 0) + 1
            scaff_counts[cat] = scaff_counts.get(cat, 0) + 1
        except Exception:
            # skip malformed entries
            continue

    def pct(count):
        return (count / total) * 100 if total > 0 else 0.0

    bloom_dist = [{"level": k, "count": v, "pct": pct(v)} for k, v in sorted(bloom_counts.items(), key=lambda x: -x[1])]
    scaff_dist = [{"category": k, "count": v, "pct": pct(v)} for k, v in sorted(scaff_counts.items(), key=lambda x: -x[1])]

    return {
        "total_analytics_records": total,
        "bloom_distribution": bloom_dist,
        "scaffolding_distribution": scaff_dist
    }
