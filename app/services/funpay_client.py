"""Async HTTP client for FunPay.

FunPay has no official public API; this client scrapes the same pages that the
website uses and POSTs to the same internal `/runner/` endpoint. Because the
underlying HTML/JSON shapes are the property of FunPay and may change at any
time, all parsing is wrapped in defensive error handling so the panel keeps
working even when individual fields go missing.

Each `FunPayClient` is bound to a single account and uses that account's
golden_key cookie, proxy URL (HTTP/SOCKS), and user-agent. Cookies / proxies /
UAs are NEVER shared between accounts.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.config import get_settings
from app.schemas.chat import ChatMessage, ChatPreview, ChatThread

log = logging.getLogger("funpay.client")

_settings = get_settings()


class FunPayError(RuntimeError):
    """Raised on any unrecoverable FunPay client error (auth, network, parse)."""


class FunPayAuthError(FunPayError):
    """Raised when the golden_key is invalid or the session is unauthenticated."""


@dataclass(frozen=True)
class FunPayCredentials:
    golden_key: str
    user_agent: str
    proxy_url: str | None = None


@dataclass
class FunPayProfile:
    user_id: int
    username: str
    csrf_token: str | None = None


def _build_httpx_client(creds: FunPayCredentials) -> httpx.AsyncClient:
    headers = {
        "User-Agent": creds.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    }
    cookies = {"golden_key": creds.golden_key, "locale": "en"}
    # httpx accepts http(s) and socks5(h) proxies natively (with the [socks] extra installed).
    proxies: str | None = creds.proxy_url or None
    return httpx.AsyncClient(
        headers=headers,
        cookies=cookies,
        proxy=proxies,
        timeout=_settings.funpay_request_timeout_seconds,
        follow_redirects=True,
        http2=False,
        trust_env=False,  # never inherit ambient HTTP_PROXY etc.
    )


def _extract_app_data(html: str) -> dict[str, Any] | None:
    """Pull the `data-app-data` JSON blob from the FunPay <body> tag (if present)."""
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    if not isinstance(body, Tag):
        return None
    raw = body.get("data-app-data")
    if not raw:
        return None
    try:
        return json.loads(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _is_unauthenticated_html(html: str) -> bool:
    # When golden_key is invalid/expired, FunPay shows the marketing landing page
    # without an authenticated user block. We use a couple of heuristics.
    if "data-app-data" not in html:
        return True
    return False


_USER_LINK_RE = re.compile(r"/users/(\d+)/?")


class FunPayClient:
    """Per-account FunPay HTTP client. Use as an async context manager."""

    def __init__(self, creds: FunPayCredentials) -> None:
        self._creds = creds
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> FunPayClient:
        self._client = _build_httpx_client(self._creds)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("FunPayClient must be used as an async context manager")
        return self._client

    async def fetch_profile(self) -> FunPayProfile:
        """Fetch the main page and resolve the authenticated user.

        Raises FunPayAuthError if the cookie is invalid; FunPayError otherwise.
        """
        url = urljoin(_settings.funpay_base_url, "/")
        try:
            resp = await self.http.get(url)
        except httpx.HTTPError as exc:
            raise FunPayError(f"Network error talking to FunPay: {exc}") from exc

        if resp.status_code >= 500:
            raise FunPayError(f"FunPay returned HTTP {resp.status_code}")
        html = resp.text
        if _is_unauthenticated_html(html):
            raise FunPayAuthError("FunPay didn't recognise the golden_key (not logged in).")

        data = _extract_app_data(html) or {}
        user = data.get("user") or {}
        user_id = user.get("id") or data.get("userId")
        username = user.get("username") or data.get("username")
        csrf = data.get("csrf-token") or data.get("csrfToken")
        if not user_id or not username:
            # Fallback: scan a "/users/<id>/" link near the header.
            soup = BeautifulSoup(html, "lxml")
            link = soup.find("a", href=_USER_LINK_RE)
            if isinstance(link, Tag):
                match = _USER_LINK_RE.search(link.get("href") or "")
                if match:
                    user_id = int(match.group(1))
                    username = (link.get_text() or "").strip() or f"user{user_id}"
        if not user_id or not username:
            raise FunPayAuthError(
                "Could not extract authenticated user from FunPay home page."
            )
        return FunPayProfile(user_id=int(user_id), username=str(username), csrf_token=csrf)

    async def list_chats(self) -> list[ChatPreview]:
        """List recent chats from the messages page."""
        url = urljoin(_settings.funpay_base_url, "/chat/")
        try:
            resp = await self.http.get(url)
        except httpx.HTTPError as exc:
            raise FunPayError(f"Network error: {exc}") from exc
        if resp.status_code != 200:
            raise FunPayError(f"FunPay returned HTTP {resp.status_code} for /chat/")

        soup = BeautifulSoup(resp.text, "lxml")
        chats: list[ChatPreview] = []
        # FunPay's chat list items use the `.contact-item` / `.chat-list` hierarchy in the
        # current UI. We support both common variants.
        seen: set[str] = set()
        candidates = soup.select("a.contact-item, a[data-id].chat-item, .chat-list a")
        for node in candidates:
            if not isinstance(node, Tag):
                continue
            chat_id = (
                node.get("data-id")
                or node.get("data-node-id")
                or node.get("data-node")
                or node.get("data-chat-id")
                or _id_from_href(node.get("href"))
            )
            if not chat_id or chat_id in seen:
                continue
            seen.add(str(chat_id))
            title_node = node.select_one(".media-user-name, .chat-name, .contact-item__username")
            preview_node = node.select_one(
                ".contact-item__message-text, .chat-message, .media-body"
            )
            title = (title_node.get_text() if title_node else node.get_text() or "").strip()
            preview = (preview_node.get_text().strip() if preview_node else None) or None
            unread_classes = (node.get("class") or [])
            unread = any("unread" in c for c in unread_classes)
            chats.append(
                ChatPreview(
                    id=str(chat_id),
                    title=title or f"chat {chat_id}",
                    last_message=preview,
                    unread=unread,
                )
            )
        return chats

    async def get_chat(self, chat_id: str) -> ChatThread:
        if not re.match(r"^[A-Za-z0-9_\-]{1,64}$", chat_id):
            raise FunPayError("Invalid chat id")
        url = urljoin(_settings.funpay_base_url, f"/chat/?node={chat_id}")
        try:
            resp = await self.http.get(url)
        except httpx.HTTPError as exc:
            raise FunPayError(f"Network error: {exc}") from exc
        if resp.status_code != 200:
            raise FunPayError(f"FunPay returned HTTP {resp.status_code} for /chat/")

        soup = BeautifulSoup(resp.text, "lxml")
        title_node = soup.select_one(".chat-header__name, .chat-full-header .media-user-name")
        title = (title_node.get_text().strip() if title_node else f"chat {chat_id}") or chat_id

        messages: list[ChatMessage] = []
        my_user_id: int | None = None
        app_data = _extract_app_data(resp.text) or {}
        user = app_data.get("user") or {}
        if isinstance(user.get("id"), int):
            my_user_id = int(user["id"])

        for node in soup.select(
            ".chat-message, .message-container, .chat-msg-item, [data-message-id]"
        ):
            if not isinstance(node, Tag):
                continue
            msg_id = node.get("data-message-id") or node.get("data-id") or None
            text_node = node.select_one(".chat-message__text, .message-text, .media-body")
            text = (text_node.get_text().strip() if text_node else node.get_text().strip()) or ""
            author_node = node.select_one(
                ".chat-message-author, .message-author, .media-user-name"
            )
            author = (author_node.get_text().strip() if author_node else None) or None
            author_link = node.select_one("a[href*='/users/']")
            is_me = False
            if author_link and isinstance(author_link, Tag):
                href = author_link.get("href") or ""
                m = _USER_LINK_RE.search(href)
                if m and my_user_id is not None and int(m.group(1)) == my_user_id:
                    is_me = True
            sent_at = _parse_message_timestamp(node)
            if not text:
                continue
            messages.append(
                ChatMessage(
                    id=str(msg_id) if msg_id else None,
                    author=author,
                    is_me=is_me,
                    text=text,
                    sent_at=sent_at,
                )
            )
        return ChatThread(id=chat_id, title=title, messages=messages)

    async def send_message(self, chat_id: str, text: str) -> None:
        """Send a chat message via the FunPay /runner/ endpoint."""
        if not re.match(r"^[A-Za-z0-9_\-]{1,64}$", chat_id):
            raise FunPayError("Invalid chat id")
        if not text or not text.strip():
            raise FunPayError("Empty message")

        # Refresh CSRF + profile each send. The runner endpoint requires the same csrf-token
        # FunPay's own JS sends, which lives on the body's data-app-data blob.
        profile = await self.fetch_profile()
        if not profile.csrf_token:
            raise FunPayError("Could not obtain CSRF token from FunPay")

        payload = {
            "action": "chat_message",
            "data": json.dumps(
                {"node": chat_id, "last_message": -1, "content": text}, ensure_ascii=False
            ),
        }
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": _settings.funpay_base_url,
            "Referer": urljoin(_settings.funpay_base_url, f"/chat/?node={chat_id}"),
            "Accept": "*/*",
        }
        runner_url = urljoin(_settings.funpay_base_url, "/runner/")
        form = {
            "objects": "",
            "request": json.dumps(payload, ensure_ascii=False),
            "csrf_token": profile.csrf_token,
        }
        try:
            resp = await self.http.post(runner_url, data=form, headers=headers)
        except httpx.HTTPError as exc:
            raise FunPayError(f"Network error sending message: {exc}") from exc

        if resp.status_code != 200:
            raise FunPayError(f"FunPay returned HTTP {resp.status_code} when sending message")
        try:
            body = resp.json()
        except ValueError as exc:
            raise FunPayError("FunPay returned a non-JSON response from /runner/") from exc
        if isinstance(body, dict) and body.get("error"):
            raise FunPayError(f"FunPay refused the message: {body['error']}")


def _id_from_href(href: object) -> str | None:
    if not isinstance(href, str):
        return None
    m = re.search(r"node=([A-Za-z0-9_\-]+)", href)
    if m:
        return m.group(1)
    m = re.search(r"/chat/(\d+)", href)
    if m:
        return m.group(1)
    return None


def _parse_message_timestamp(node: Tag) -> datetime | None:
    ts = node.get("data-time") or node.get("data-timestamp")
    if isinstance(ts, str) and ts.isdigit():
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    return None
