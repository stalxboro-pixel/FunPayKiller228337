import { Link, NavLink, Outlet } from "react-router-dom";
import { type Me } from "../api";
import ThemeToggle from "./ThemeToggle";

type Props = {
  me: Me;
  onLogout: () => void;
};

const NAV: Array<{
  to: string;
  label: string;
  end?: boolean;
  icon: string;
}> = [
  { to: "/", label: "Home", end: true, icon: "🏠" },
  { to: "/accounts", label: "Acct", icon: "👤" },
  { to: "/chats", label: "Chat", icon: "💬" },
  { to: "/plugins", label: "Plug", icon: "🧩" },
];

export default function Layout({ me, onLogout }: Props) {
  return (
    <div className="grid h-full min-h-screen grid-cols-[112px_1fr] gap-4 p-4">
      <aside className="neu flex flex-col items-stretch gap-3 p-3">
        <Link
          to="/"
          className="grid h-10 w-10 mx-auto place-items-center rounded-xl bg-surface text-ink shadow-neu-sm font-black"
          title={`FunPay Killer · ${me.username}`}
        >
          F
        </Link>
        <nav className="flex flex-col gap-1.5">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              title={item.label}
              className={({ isActive }) =>
                isActive
                  ? "flex flex-col items-center gap-0.5 rounded-xl px-1 py-2 text-[10px] uppercase tracking-wider text-ink shadow-neu-pressed bg-surface"
                  : "flex flex-col items-center gap-0.5 rounded-xl px-1 py-2 text-[10px] uppercase tracking-wider text-ink2 transition-shadow hover:text-ink"
              }
            >
              <span aria-hidden className="text-lg leading-none">
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto flex flex-col items-center gap-2">
          <div
            className="truncate text-center text-[10px] text-muted"
            title={me.username}
          >
            {me.username}
          </div>
          <button
            onClick={onLogout}
            className="btn-icon"
            title="Log out"
            aria-label="Log out"
          >
            ⏻
          </button>
        </div>
      </aside>
      <main className="relative min-w-0">
        {/* Theme toggle floats in the top-right of the main pane so it stays
            anchored regardless of which page is open. */}
        <div className="pointer-events-none absolute right-0 top-0 z-10 flex justify-end">
          <div className="pointer-events-auto">
            <ThemeToggle />
          </div>
        </div>
        <Outlet />
      </main>
    </div>
  );
}
