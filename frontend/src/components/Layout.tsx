import { Link, NavLink, Outlet } from "react-router-dom";
import { type Me } from "../api";

type Props = {
  me: Me;
  onLogout: () => void;
};

export default function Layout({ me, onLogout }: Props) {
  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <Link to="/" className="flex items-center gap-3">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-accent to-accent2 text-bg font-black">
            F
          </span>
          <span className="text-lg font-semibold tracking-wide">
            FunPay <span className="text-muted">Killer</span>
          </span>
        </Link>
        <nav className="flex items-center gap-2 text-sm">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `btn-ghost ${isActive ? "border-accent text-accent" : ""}`
            }
          >
            Dashboard
          </NavLink>
          <NavLink
            to="/accounts"
            className={({ isActive }) =>
              `btn-ghost ${isActive ? "border-accent text-accent" : ""}`
            }
          >
            Accounts
          </NavLink>
          <span className="ml-3 text-muted">
            <span className="text-slate-300">{me.username}</span>
          </span>
          <button onClick={onLogout} className="btn-ghost">
            Log out
          </button>
        </nav>
      </header>
      <main className="flex-1 px-6 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-border px-6 py-4 text-center text-xs text-muted">
        Bound to localhost only · Encrypted credentials at rest · MVP
      </footer>
    </div>
  );
}
