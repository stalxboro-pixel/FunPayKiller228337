"""Async HTTP client for FunPay.

FunPay has no official public API; this client talks to the same endpoints the
website uses (`/`, `/runner/`, `/chat/history`) and authenticates with a single
`golden_key` cookie. Each `FunPayClient` is bound to one account and uses that
account's cookie, proxy URL (HTTP/HTTPS/SOCKS) and user-agent — credentials
are *never* shared between accounts.

Reference: https://github.com/LIMBODS/FunPayAPI (GPL-3.0) — used for
endpoint reverse-engineering only; no source is copied.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
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


class FunPayMessageRejected(FunPayError):
    """Raised when FunPay accepts the request but rejects the message itself."""


@dataclass(frozen=True)
class FunPayCredentials:
    golden_key: str
    user_agent: str
    proxy_url: str | None = None


@dataclass
class FunPayProfile:
    user_id: int
    username: str
    csrf_token: str


def _build_httpx_client(creds: FunPayCredentials) -> httpx.AsyncClient:
    headers = {
        "User-Agent": creds.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    }
    cookies = {"golden_key": creds.golden_key, "locale": "en"}
    return httpx.AsyncClient(
        headers=headers,
        cookies=cookies,
        proxy=creds.proxy_url or None,
        timeout=_settings.funpay_request_timeout_seconds,
        follow_redirects=True,
        http2=False,
        trust_env=False,  # never inherit ambient HTTP_PROXY etc.
    )


def _extract_app_data(html: str, soup: BeautifulSoup | None = None) -> dict[str, Any] | None:
    """Pull the `data-app-data` JSON blob from the FunPay <body> tag (if present)."""
    if soup is None:
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


_CHAT_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
_USER_LINK_RE = re.compile(r"/users/(\d+)/?")


def _coerce_chat_id(chat_id: str) -> int | str:
    """FunPay treats numeric chat ids as ints; private chats use `users-<a>-<b>`."""
    if chat_id.isdigit():
        return int(chat_id)
    return chat_id


def _random_tag() -> str:
    return secrets.token_hex(4)


class FunPayClient:
    """Per-account FunPay HTTP client. Use as an async context manager."""

    def __init__(self, creds: FunPayCredentials) -> None:
        self._creds = creds
        self._client: httpx.AsyncClient | None = None
        self._profile: FunPayProfile | None = None

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

    # ------------------------------------------------------------------
    # Profile / CSRF
    # ------------------------------------------------------------------

    async def fetch_profile(self, *, force: bool = False) -> FunPayProfile:
        """Fetch the main page, resolve the authenticated user + CSRF token.

        Memoised on the client instance — only the first call hits the network
        unless `force=True`. Raises FunPayAuthError if golden_key is invalid.
        """
        if self._profile is not None and not force:
            return self._profile

        url = urljoin(_settings.funpay_base_url, "/")
        try:
            resp = await self.http.get(url)
        except httpx.HTTPError as exc:
            raise FunPayError(f"Network error talking to FunPay: {exc}") from exc

        if resp.status_code >= 500:
            raise FunPayError(f"FunPay returned HTTP {resp.status_code}")
        html = resp.text
        if "data-app-data" not in html:
            raise FunPayAuthError("FunPay didn't recognise the golden_key (not logged in).")

        soup = BeautifulSoup(html, "lxml")
        data = _extract_app_data(html, soup) or {}
        user_id_raw = data.get("userId") or (data.get("user") or {}).get("id")
        csrf = data.get("csrf-token") or data.get("csrfToken")
        username: str | None = None
        username_node = soup.select_one(".user-link-name, .header-user-name")
        if username_node:
            username = username_node.get_text(strip=True) or None
        if not username:
            link = soup.find("a", href=_USER_LINK_RE)
            if isinstance(link, Tag):
                username = (link.get_text() or "").strip() or None
        if not user_id_raw or not username or not csrf:
            raise FunPayAuthError(
                "Could not extract authenticated user / CSRF token from FunPay home page."
            )
        self._profile = FunPayProfile(
            user_id=int(user_id_raw), username=str(username), csrf_token=str(csrf)
        )
        return self._profile

    # ------------------------------------------------------------------
    # Chat list (via /runner/ chat_bookmarks — much cheaper than scraping /chat/)
    # ------------------------------------------------------------------

    async def list_chats(self) -> list[ChatPreview]:
        profile = await self.fetch_profile()
        objects = [
            {
                "type": "chat_bookmarks",
                "id": profile.user_id,
                "tag": _random_tag(),
                "data": False,
            }
        ]
        body = await self._runner_post(objects=objects, request=False, csrf=profile.csrf_token)

        # Find the bookmarks object regardless of order.
        html_blob = ""
        for obj in body.get("objects") or []:
            if obj.get("type") == "chat_bookmarks":
                data = obj.get("data") or {}
                html_blob = data.get("html") or ""
                break
        if not html_blob:
            return []

        soup = BeautifulSoup(html_blob, "lxml")
        previews: list[ChatPreview] = []
        for node in soup.select("a.contact-item"):
            chat_id = node.get("data-id")
            if not chat_id:
                continue
            title_node = node.select_one(".media-user-name")
            preview_node = node.select_one(".contact-item-message")
            classes = node.get("class") or []
            title = (title_node.get_text(strip=True) if title_node else "") or f"chat {chat_id}"
            preview = preview_node.get_text(strip=True) if preview_node else None
            unread = "unread" in classes
            previews.append(
                ChatPreview(
                    id=str(chat_id),
                    title=title,
                    last_message=preview or None,
                    unread=unread,
                )
            )
        return previews

    # ------------------------------------------------------------------
    # Chat history (JSON endpoint — far faster than the HTML chat page)
    # ------------------------------------------------------------------

    async def get_chat(self, chat_id: str, *, last_message_id: int | None = None) -> ChatThread:
        if not _CHAT_ID_RE.match(chat_id):
            raise FunPayError("Invalid chat id")
        profile = await self.fetch_profile()
        coerced = _coerce_chat_id(chat_id)
        last = last_message_id if last_message_id is not None else 99999999999
        url = urljoin(_settings.funpay_base_url, "/chat/history")
        try:
            resp = await self.http.get(
                url,
                params={"node": coerced, "last_message": last},
                headers={
                    "Accept": "*/*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": urljoin(_settings.funpay_base_url, f"/chat/?node={coerced}"),
                },
            )
        except httpx.HTTPError as exc:
            raise FunPayError(f"Network error: {exc}") from exc
        if resp.status_code != 200:
            raise FunPayError(f"FunPay returned HTTP {resp.status_code} for /chat/history")
        try:
            body = resp.json()
        except ValueError as exc:
            raise FunPayError("FunPay returned non-JSON for /chat/history") from exc

        chat = body.get("chat") or {}
        node_info = chat.get("node") or {}
        title = node_info.get("name") or f"chat {chat_id}"
        # Try to derive a human title from the messages' author block.
        messages_json = chat.get("messages") or []

        msgs: list[ChatMessage] = []
        interlocutor_name: str | None = None
        for raw in messages_json:
            html_blob = raw.get("html") or ""
            author_id = raw.get("author")
            soup = BeautifulSoup(html_blob, "lxml")
            text_node = soup.select_one(
                ".message-text, .alert.alert-with-icon.alert-info, .chat-img-link"
            )
            text = (text_node.get_text(strip=True) if text_node else "").strip()
            if not text:
                # Fallback to plain stripped HTML if structured selectors missed.
                text = soup.get_text(strip=True)
            author_node = soup.select_one(".media-user-name a, .chat-msg-author")
            author = (author_node.get_text(strip=True) if author_node else None) or None
            if author and not interlocutor_name and author_id != profile.user_id:
                interlocutor_name = author
            sent_at = _parse_message_timestamp(raw)
            msgs.append(
                ChatMessage(
                    id=str(raw.get("id")) if raw.get("id") is not None else None,
                    author=author,
                    is_me=(author_id == profile.user_id),
                    text=text,
                    sent_at=sent_at,
                )
            )
        if interlocutor_name:
            title = interlocutor_name
        return ChatThread(id=chat_id, title=title, messages=msgs)

    # ------------------------------------------------------------------
    # Send message
    # ------------------------------------------------------------------

    async def send_message(self, chat_id: str, text: str) -> None:
        if not _CHAT_ID_RE.match(chat_id):
            raise FunPayError("Invalid chat id")
        if not text or not text.strip():
            raise FunPayError("Empty message")
        profile = await self.fetch_profile()
        coerced = _coerce_chat_id(chat_id)

        request = {
            "action": "chat_message",
            "data": {"node": coerced, "last_message": -1, "content": text},
        }
        objects = [
            {
                "type": "chat_node",
                "id": coerced,
                "tag": _random_tag(),
                "data": {"node": coerced, "last_message": -1, "content": ""},
            }
        ]
        body = await self._runner_post(
            objects=objects,
            request=request,
            csrf=profile.csrf_token,
            referer=f"/chat/?node={coerced}",
        )

        # Successful runner response: {"response": {...}, "objects": [...]}
        response_obj = body.get("response")
        if not isinstance(response_obj, dict):
            # If the CSRF expired, FunPay sometimes returns an error/redirect; force-refresh
            # and try once more.
            await self.fetch_profile(force=True)
            raise FunPayMessageRejected(
                "FunPay didn't return a runner response — message likely not delivered."
            )
        error_text = response_obj.get("error")
        if error_text:
            # Common cause: stale CSRF token. Re-fetch and retry once.
            if "csrf" in str(error_text).lower():
                await self.fetch_profile(force=True)
                request["data"]["node"] = coerced  # type: ignore[index]
                body = await self._runner_post(
                    objects=objects,
                    request=request,
                    csrf=self._profile.csrf_token if self._profile else profile.csrf_token,
                    referer=f"/chat/?node={coerced}",
                )
                response_obj = body.get("response") or {}
                if response_obj.get("error"):
                    raise FunPayMessageRejected(str(response_obj["error"]))
                return
            raise FunPayMessageRejected(str(error_text))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _runner_post(
        self,
        *,
        objects: list[dict[str, Any]] | bool,
        request: dict[str, Any] | bool,
        csrf: str,
        referer: str | None = None,
    ) -> dict[str, Any]:
        url = urljoin(_settings.funpay_base_url, "/runner/")
        form = {
            "objects": json.dumps(objects, ensure_ascii=False) if objects is not False else "",
            "request": json.dumps(request, ensure_ascii=False) if request is not False else "false",
            "csrf_token": csrf,
        }
        headers: dict[str, str] = {
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": _settings.funpay_base_url,
        }
        if referer:
            headers["Referer"] = urljoin(_settings.funpay_base_url, referer)
        try:
            resp = await self.http.post(url, data=form, headers=headers)
        except httpx.HTTPError as exc:
            raise FunPayError(f"Network error: {exc}") from exc
        if resp.status_code == 401 or resp.status_code == 403:
            raise FunPayAuthError(f"FunPay refused /runner/ ({resp.status_code})")
        if resp.status_code != 200:
            raise FunPayError(f"FunPay /runner/ returned HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise FunPayError("FunPay returned a non-JSON response from /runner/") from exc
        if not isinstance(data, dict):
            raise FunPayError("Unexpected /runner/ response shape (not an object)")
        return data


def _parse_message_timestamp(raw: dict[str, Any]) -> datetime | None:
    for key in ("createdAt", "created_at", "time", "date"):
        v = raw.get(key)
        if isinstance(v, (int, float)) and v > 0:
            try:
                return datetime.fromtimestamp(int(v), tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                return None
    return None
