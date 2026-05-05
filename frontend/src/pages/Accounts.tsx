import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, type Account, type AccountCreate, type AccountCheckResult } from "../api";

const DEFAULT_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

export default function Accounts() {
  const [items, setItems] = useState<Account[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    try {
      setItems(await api.get<Account[]>("/api/accounts"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-wide">FunPay accounts</h1>
          <p className="text-sm text-muted">
            golden_key, proxy and user-agent are stored encrypted on disk.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "+ Add account"}
        </button>
      </header>
      {err && <div className="text-sm text-rose-400">{err}</div>}
      {showForm && (
        <AddAccountForm
          onCancel={() => setShowForm(false)}
          onCreated={async () => {
            setShowForm(false);
            await refresh();
          }}
        />
      )}
      <section className="space-y-3">
        {items === null ? (
          <div className="text-sm text-muted">Loading…</div>
        ) : items.length === 0 ? (
          <div className="card text-sm text-muted">
            No accounts yet. Add one to start managing chats.
          </div>
        ) : (
          items.map((a) => (
            <AccountCard key={a.id} account={a} onChanged={refresh} />
          ))
        )}
      </section>
    </div>
  );
}

function AddAccountForm({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState<AccountCreate>({
    label: "",
    golden_key: "",
    proxy_url: "",
    user_agent: DEFAULT_UA,
    note: "",
  });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function update<K extends keyof AccountCreate>(k: K, v: AccountCreate[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const payload: AccountCreate = {
        ...form,
        proxy_url: form.proxy_url ? form.proxy_url : null,
        note: form.note ? form.note : null,
      };
      await api.post<Account>("/api/accounts", payload);
      onCreated();
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card grid gap-4 md:grid-cols-2">
      <div className="md:col-span-1">
        <label className="label">Label</label>
        <input
          className="input"
          value={form.label}
          onChange={(e) => update("label", e.target.value)}
          required
        />
      </div>
      <div className="md:col-span-1">
        <label className="label">golden_key (FunPay cookie)</label>
        <input
          className="input font-mono"
          value={form.golden_key}
          onChange={(e) => update("golden_key", e.target.value)}
          required
          minLength={16}
          spellCheck={false}
        />
      </div>
      <div className="md:col-span-2">
        <label className="label">Proxy URL (optional, scheme://[user:pass@]host:port)</label>
        <input
          className="input font-mono"
          value={form.proxy_url ?? ""}
          onChange={(e) => update("proxy_url", e.target.value)}
          placeholder="http://user:pass@host:8000  •  socks5://host:1080"
          spellCheck={false}
        />
      </div>
      <div className="md:col-span-2">
        <label className="label">User-Agent</label>
        <input
          className="input font-mono"
          value={form.user_agent}
          onChange={(e) => update("user_agent", e.target.value)}
          required
          spellCheck={false}
        />
      </div>
      <div className="md:col-span-2">
        <label className="label">Note (optional)</label>
        <input
          className="input"
          value={form.note ?? ""}
          onChange={(e) => update("note", e.target.value)}
        />
      </div>
      {err && <div className="md:col-span-2 text-sm text-rose-400">{err}</div>}
      <div className="md:col-span-2 flex justify-end gap-2">
        <button type="button" className="btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn-primary" disabled={busy}>
          {busy ? "Saving…" : "Save account"}
        </button>
      </div>
    </form>
  );
}

function AccountCard({
  account,
  onChanged,
}: {
  account: Account;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [check, setCheck] = useState<AccountCheckResult | null>(null);

  async function probe() {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.post<AccountCheckResult>(
        `/api/accounts/${account.id}/check`
      );
      setCheck(r);
      onChanged();
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function toggleEnabled() {
    setBusy(true);
    try {
      await api.patch(`/api/accounts/${account.id}`, {
        enabled: !account.enabled,
      });
      onChanged();
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function destroy() {
    if (!confirm(`Delete account "${account.label}"?`)) return;
    setBusy(true);
    try {
      await api.del(`/api/accounts/${account.id}`);
      onChanged();
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  const statusText =
    check?.error ??
    account.last_check_error ??
    (account.last_check_ok ? "Healthy" : "Not checked");

  return (
    <div className="card flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold">{account.label}</h3>
          <span
            className={`rounded-full px-2 py-0.5 text-xs ${
              account.enabled
                ? "bg-emerald-500/10 text-emerald-300"
                : "bg-slate-500/10 text-slate-400"
            }`}
          >
            {account.enabled ? "enabled" : "disabled"}
          </span>
          {account.proxy_present ? (
            <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-xs text-cyan-300">
              proxy
            </span>
          ) : null}
        </div>
        <div className="text-sm text-muted">
          {account.funpay_username ? (
            <>
              FunPay: <span className="text-slate-200">{account.funpay_username}</span>
              {account.funpay_user_id ? <> · #{account.funpay_user_id}</> : null}
            </>
          ) : (
            <>FunPay: not yet probed</>
          )}
        </div>
        <div className="mt-1 text-xs">
          <span
            className={`mr-2 ${
              account.last_check_ok ? "text-emerald-300" : "text-rose-300"
            }`}
          >
            ●
          </span>
          {statusText}
          {account.note ? <span className="ml-2 text-muted">— {account.note}</span> : null}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Link
          className="btn-ghost"
          to={`/accounts/${account.id}/chats`}
          aria-disabled={!account.enabled}
        >
          Open chats
        </Link>
        <button className="btn-ghost" onClick={probe} disabled={busy}>
          {busy ? "…" : "Check"}
        </button>
        <button className="btn-ghost" onClick={toggleEnabled} disabled={busy}>
          {account.enabled ? "Disable" : "Enable"}
        </button>
        <button className="btn-danger" onClick={destroy} disabled={busy}>
          Delete
        </button>
      </div>
      {err && <div className="md:col-span-2 text-sm text-rose-400">{err}</div>}
    </div>
  );
}
