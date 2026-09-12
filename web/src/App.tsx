import { Link, NavLink, Navigate, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./auth";
import { Button, Chip } from "./components/ui";
import type { IconProps } from "./icons";
import {
  ActivityIcon,
  CampaignIcon,
  GridIcon,
  MonitorIcon,
  PlayIcon,
  ReviewIcon,
  SettingsIcon,
  StitchIcon,
  UploadIcon,
} from "./icons";
import CampaignDetail from "./pages/CampaignDetail";
import Campaigns from "./pages/Campaigns";
import Jobs from "./pages/Jobs";
import Login from "./pages/Login";
import Montage from "./pages/Montage";
import Projects from "./pages/Projects";
import Review from "./pages/Review";
import Settings from "./pages/Settings";
import Studio from "./pages/Studio";
import System from "./pages/System";

interface NavItem {
  to: string;
  label: string;
  icon: (props: IconProps) => ReactNode;
}

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Make",
    items: [
      { to: "/", label: "Studio", icon: UploadIcon },
      { to: "/review", label: "Review", icon: ReviewIcon },
      { to: "/montage", label: "Montage", icon: StitchIcon },
      { to: "/jobs", label: "Jobs", icon: ActivityIcon },
    ],
  },
  {
    section: "Ship",
    items: [
      { to: "/projects", label: "Library", icon: GridIcon },
      { to: "/campaigns", label: "Campaigns", icon: CampaignIcon },
    ],
  },
  {
    section: "Run",
    items: [
      { to: "/system", label: "System", icon: MonitorIcon },
      { to: "/settings", label: "Settings", icon: SettingsIcon },
    ],
  },
];

function Mark() {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-primary/15 text-primary">
        <PlayIcon size={18} />
      </span>
      <span className="text-[15px] font-bold tracking-tight text-ink">
        Repurpose<span className="text-primary">AI</span>
      </span>
    </Link>
  );
}

function SidebarFooter({
  mode,
  user,
  onLogout,
}: {
  mode: "open" | "auth";
  user: string | null;
  onLogout: () => void;
}) {
  return (
    <div className="mt-auto border-t border-line pt-3">
      {mode === "auth" ? (
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-3 text-[11px] font-bold text-ink">
            {(user || "o").slice(0, 1).toUpperCase()}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-semibold text-ink">{user ?? "operator"}</div>
            <div className="text-[10px] uppercase tracking-[0.12em] text-faint">token session</div>
          </div>
          <button
            onClick={onLogout}
            className="text-[11px] text-faint underline decoration-dotted underline-offset-2 hover:text-muted"
          >
            sign out
          </button>
        </div>
      ) : (
        <div className="flex items-center justify-between gap-2">
          <div className="truncate text-[13px] font-semibold text-ink">Local shell</div>
          <Chip>no auth</Chip>
        </div>
      )}
    </div>
  );
}

function Shell({
  mode,
  user,
  onLogout,
}: {
  mode: "open" | "auth";
  user: string | null;
  onLogout: () => void;
}) {
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 flex-col border-r border-line bg-surface/40 px-3 py-4 lg:flex">
        <div className="px-2 pb-5">
          <Mark />
          <div className="mono mt-1.5 pl-1 text-[10px] uppercase tracking-[0.14em] text-faint">
            the cutting room
          </div>
        </div>
        <nav className="flex-1 space-y-5">
          {NAV.map((group) => (
            <div key={group.section}>
              <div className="mono px-3 pb-1.5 text-[10px] uppercase tracking-[0.16em] text-faint/70">
                {group.section}
              </div>
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 rounded-[10px] px-3 py-2 text-sm transition-colors duration-150 ease-out ${
                        isActive
                          ? "bg-surface-2 font-semibold text-ink"
                          : "text-muted hover:bg-surface-2/60 hover:text-body"
                      }`
                    }
                  >
                    <item.icon size={16} />
                    <span>{item.label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <SidebarFooter mode={mode} user={user} onLogout={onLogout} />
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-bg/85 px-4 py-2.5 backdrop-blur sm:px-6 lg:hidden">
          <Mark />
          <div className="flex items-center gap-1">
            {NAV.flatMap((g) => g.items).map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                aria-label={item.label}
                className={({ isActive }) =>
                  `flex h-9 w-9 items-center justify-center rounded-[10px] transition-colors duration-150 ${
                    isActive ? "bg-surface-2 text-ink" : "text-faint"
                  }`
                }
              >
                <item.icon size={17} />
              </NavLink>
            ))}
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1180px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Routes>
            <Route path="/" element={<Studio />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/review" element={<Review />} />
            <Route path="/montage" element={<Montage />} />
            <Route path="/campaigns" element={<Campaigns />} />
            <Route path="/campaign/:id" element={<CampaignDetail />} />
            <Route path="/exports" element={<Navigate to="/projects" replace />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/system" element={<System />} />
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function Splash() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/15 text-primary">
        <PlayIcon size={26} />
      </span>
      <div className="flex items-center gap-2.5 text-sm text-faint">
        <span className="inline-block h-2 w-2 animate-pulse-soft rounded-full bg-primary" />
        Connecting to the cutting room
      </div>
    </div>
  );
}

function Offline({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-line bg-surface p-6 text-center shadow-ambient-sm">
        <div className="text-base font-semibold text-ink">Server unreachable</div>
        <div className="mt-1.5 text-sm text-faint">
          The API host did not answer. Make sure it is up, then try again.
        </div>
        <Button variant="primary" className="mt-5" onClick={onRetry}>
          Try again
        </Button>
      </div>
    </div>
  );
}

function Gate() {
  const { status, mode, user, logout, reprobe } = useAuth();
  if (status === "checking") return <Splash />;
  if (status === "offline") return <Offline onRetry={reprobe} />;
  if (status === "auth") return <Login />;
  return <Shell mode={mode} user={user} onLogout={() => void logout()} />;
}

export default function App() {
  return <Gate />;
}