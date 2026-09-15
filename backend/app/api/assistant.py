"""Spotter AI Assistant API — Phase 29 (PRD Sections 26–27, 37).

POST /api/v1/assistant/chat  — natural-language query over the real
backend modules. Accepts {message, conversation_history} and returns
{response, functions_called, data_sources_used} so the frontend can show
transparency ("this answer is based on: ...").
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.assistant_service import chat, read_audit

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="The user's question.")
    conversation_history: list[ChatTurn] | None = Field(
        default=None,
        description="Rolling multi-turn context (user/assistant pairs).",
    )


class ChatResponse(BaseModel):
    response: str
    functions_called: list[str]
    data_sources_used: list[str]


@router.post("/chat", response_model=ChatResponse)
def assistant_chat(payload: ChatRequest) -> dict:
    """Full assistant turn: classify -> call backend functions -> answer."""
    history = (
        [{"role": t.role, "content": t.content} for t in payload.conversation_history]
        if payload.conversation_history
        else None
    )
    return chat(payload.message, history)


@router.get("/audit")
def assistant_audit(limit: int = Query(50, ge=1, le=500)) -> dict:
    """Grounding audit log: responses alongside the functions called."""
    entries = read_audit(limit)
    return {"count": len(entries), "entries": entries}
