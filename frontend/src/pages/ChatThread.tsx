import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api, type ChatThread } from "../api";

export default function ChatThreadPage() {
  const { accountId, chatId } = useParams<{
    accountId: string;
    chatId: string;
  }>();
  const [thread, setThread] = useState<ChatThread | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  async function refresh() {
    if (!accountId || !chatId) return;
    setErr(null);
    try {
      const t = await api.get<ChatThread>(
        `/api/accounts/${accountId}/chats/${encodeURIComponent(chatId)}`
      );
      setThread(t);
      setTimeout(
        () => endRef.current?.scrollIntoView({ behavior: "smooth" }),
        50
      );
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId, chatId]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!accountId || !chatId || !text.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await api.post(
        `/api/accounts/${accountId}/chats/${encodeURIComponent(chatId)}/messages`,
        { text: text.trim() }
      );
      setText("");
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-wide">
            {thread?.title ?? "Loading…"}
          </h1>
          <p className="text-sm text-muted">FunPay chat #{chatId}</p>
        </div>
        <Link to={`/accounts/${accountId}/chats`} className="btn-ghost">
          ← Back to chats
        </Link>
      </header>
      <div className="card max-h-[60vh] overflow-y-auto">
        {err && <div className="text-sm text-rose-400">{err}</div>}
        {thread === null ? (
          <div className="text-sm text-muted">Loading…</div>
        ) : thread.messages.length === 0 ? (
          <div className="text-sm text-muted">No messages.</div>
        ) : (
          <ul className="space-y-3">
            {thread.messages.map((m, i) => (
              <li
                key={(m.id ?? "") + i}
                className={`flex ${m.is_me ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[75%] rounded-2xl border border-border px-4 py-2 text-sm ${
                    m.is_me
                      ? "bg-accent/10 text-slate-100"
                      : "bg-panel text-slate-100"
                  }`}
                >
                  {m.author && !m.is_me ? (
                    <div className="text-xs text-muted">{m.author}</div>
                  ) : null}
                  <div className="whitespace-pre-wrap break-words">{m.text}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
        <div ref={endRef} />
      </div>
      <form onSubmit={send} className="card flex flex-col gap-2 md:flex-row md:items-end">
        <textarea
          className="input min-h-[3rem]"
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type a message…"
          maxLength={4000}
        />
        <button className="btn-primary md:w-32" disabled={busy || !text.trim()}>
          {busy ? "Sending…" : "Send"}
        </button>
      </form>
    </div>
  );
}
