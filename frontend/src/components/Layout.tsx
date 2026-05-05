import { Link, NavLink, Outlet } from "react-router-dom";
import { type Me } from "../api";

type Props = {
  me: Me;
  onLogout: () => void;
};

const NAV: Array<{ to: string; label: string; end?: boolean }> = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/accounts", label: "Accounts" },
  { to: "/chats", label: "Chats" },
  { to: "/plugins", label: "Plugins" },
];

export default function Layout({ me, onLogout }: Props) {
  return (
    <div className="grid h-full min-h-screen grid-cols-[260px_1fr] gap-6 p-6">
      <aside className="neu flex flex-col gap-4 p-5">
        <Link to="/" className="flex items-center gap-3 px-1 py-1">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-surface text-ink shadow-neu-sm font-black">
            F
          </span>
          <span className="text-base font-semibold tracking-wide">
            FunPay <span className="text-muted">Killer</span>
          </span>
        </Link>
        <nav className="flex flex-col gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive ? "nav-link nav-link-active" : "nav-link"
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto neu-inset p-3 text-[11px] leading-relaxed text-muted">
          <div className="text-ink2">
            <span className="text-ink">{me.username}</span>
          </div>
          <div className="mt-1">Localhost only · Encrypted at rest</div>
        </div>
        <button onClick={onLogout} className="btn-primary w-full">
          Log out
        </button>
      </aside>
      <main className="min-w-0">
        <Outlet />
      </main>
    </div>
  );
}
