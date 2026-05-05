"""Chat list / messages / send-message routes (per FunPay account)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.account import Account
from app.schemas.chat import ChatPreview, ChatThread, SendMessageRequest
from app.security import get_current_user, require_csrf
from app.services.account_service import credentials_for
from app.services.funpay_client import (
    FunPayAuthError,
    FunPayClient,
    FunPayError,
)

router = APIRouter(
    prefix="/api/accounts/{account_id}",
    tags=["chats"],
    dependencies=[Depends(get_current_user)],
)


def _account_or_404(account_id: int, db: Session) -> Account:
    a = db.get(Account, account_id)
    if a is None or not a.enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return a


@router.get("/chats", response_model=list[ChatPreview])
async def list_chats(account_id: int, db: Session = Depends(get_db)) -> list[ChatPreview]:
    account = _account_or_404(account_id, db)
    try:
        async with FunPayClient(credentials_for(account)) as client:
            return await client.list_chats()
    except FunPayAuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except FunPayError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/chats/{chat_id}", response_model=ChatThread)
async def get_chat(account_id: int, chat_id: str, db: Session = Depends(get_db)) -> ChatThread:
    account = _account_or_404(account_id, db)
    try:
        async with FunPayClient(credentials_for(account)) as client:
            return await client.get_chat(chat_id)
    except FunPayAuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except FunPayError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post(
    "/chats/{chat_id}/messages",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def send_message(
    account_id: int,
    chat_id: str,
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
) -> None:
    account = _account_or_404(account_id, db)
    try:
        async with FunPayClient(credentials_for(account)) as client:
            await client.send_message(chat_id, payload.text)
    except FunPayAuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except FunPayError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
