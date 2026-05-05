import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api, type ChatPreview } from "../api";

export default function AccountChats() {
  const { accountId } = useParams<{ accountId: string }>();
  const [chats, setChats] = useState<ChatPreview[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    if (!accountId) return;
    setBusy(true);
    setErr(null);
    try {
      setChats(await api.get<ChatPreview[]>(`/api/accounts/${accountId}/chats`));
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId]);

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-wide">Chats</h1>
          <p className="text-sm text-muted">Recent conversations on FunPay.</p>
        </div>
        <div className="flex gap-2">
          <Link to="/accounts" className="btn-ghost">
            ← Back to accounts
          </Link>
          <button onClick={refresh} className="btn-primary" disabled={busy}>
            {busy ? "…" : "Refresh"}
          </button>
        </div>
      </header>
      {err && <div className="text-sm text-rose-400">{err}</div>}
      {chats === null ? (
        <div className="text-sm text-muted">Loading…</div>
      ) : chats.length === 0 ? (
        <div className="card text-sm text-muted">No chats yet.</div>
      ) : (
        <ul className="space-y-2">
          {chats.map((c) => (
            <li key={c.id}>
              <Link
                to={`/accounts/${accountId}/chats/${c.id}`}
                className="card flex items-center justify-between hover:border-accent"
              >
                <div>
                  <div className="font-medium">
                    {c.title}{" "}
                    {c.unread && (
                      <span className="ml-2 rounded-full bg-accent/20 px-2 py-0.5 text-xs text-accent">
                        unread
                      </span>
                    )}
                  </div>
                  {c.last_message ? (
                    <div className="line-clamp-1 text-sm text-muted">
                      {c.last_message}
                    </div>
                  ) : null}
                </div>
                <span className="text-xs text-muted">→</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
