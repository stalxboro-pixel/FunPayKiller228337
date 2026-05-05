"""Schemas for FunPay chat endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class ChatPreview(BaseModel):
    id: str
    title: str
    last_message: str | None = None
    unread: bool = False


class ChatMessage(BaseModel):
    id: str | None = None
    author: str | None = None
    is_me: bool = False
    text: str
    sent_at: datetime | None = None


class ChatThread(BaseModel):
    id: str
    title: str
    messages: list[ChatMessage]


class SendMessageRequest(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=4000)]
