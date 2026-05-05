import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Account, type PluginInfo } from "../api";

export default function Dashboard() {
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [plugins, setPlugins] = useState<PluginInfo[] | null>(null);

  useEffect(() => {
    void Promise.all([
      api.get<Account[]>("/api/accounts"),
      api.get<PluginInfo[]>("/api/plugins"),
    ]).then(([a, p]) => {
      setAccounts(a);
      setPlugins(p);
    });
  }, []);

  const total = accounts?.length ?? 0;
  const ok = accounts?.filter((a) => a.last_check_ok).length ?? 0;
  const enabled = accounts?.filter((a) => a.enabled).length ?? 0;

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl font-semibold tracking-wide">Overview</h1>
        <p className="text-sm text-muted">
          MVP scope: secure account management, messaging, and a plugin contract.
          Market dashboards and seller analytics will arrive as plugins.
        </p>
      </section>
      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card title="Accounts" value={total} hint="Configured" />
        <Card title="Enabled" value={enabled} hint="Active" />
        <Card title="Healthy" value={ok} hint="Last probe OK" />
      </section>
      <section className="card">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Quick links</h2>
          <Link to="/accounts" className="btn-primary">
            Manage accounts
          </Link>
        </div>
        <ul className="text-sm text-muted">
          <li>· Add a FunPay account with its own proxy and user-agent.</li>
          <li>· Open chats and reply directly from this panel.</li>
          <li>· Plugins (auto-lift, auto-deliver, dashboards) plug into the same UI.</li>
        </ul>
      </section>
      <section className="card">
        <h2 className="mb-3 text-lg font-semibold">Plugins</h2>
        {plugins === null ? (
          <div className="text-sm text-muted">Loading…</div>
        ) : plugins.length === 0 ? (
          <div className="text-sm text-muted">
            No plugins installed. The MVP intentionally ships zero plugins; the
            interface is defined in <code>app/plugins/base.py</code>.
          </div>
        ) : (
          <ul className="grid gap-2 md:grid-cols-2">
            {plugins.map((p) => (
              <li key={p.slug} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{p.name}</span>
                  <span className="text-xs text-muted">{p.version}</span>
                </div>
                <p className="text-sm text-muted">{p.description}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Card({
  title,
  value,
  hint,
}: {
  title: string;
  value: number;
  hint: string;
}) {
  return (
    <div className="card">
      <div className="text-xs uppercase tracking-wider text-muted">{title}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-muted">{hint}</div>
    </div>
  );
}
