import { Link, Route, Routes, useLocation } from "react-router-dom";
import Exports from "./pages/Exports";
import Jobs from "./pages/Jobs";
import Overview from "./pages/Overview";
import Projects from "./pages/Projects";
import Review from "./pages/Review";
import Settings from "./pages/Settings";
import System from "./pages/System";

const NAV = [
  ["Overview", "/"], ["Projects", "/projects"], ["Jobs", "/jobs"],
  ["Review", "/review"], ["Exports", "/exports"], ["Settings", "/settings"], ["System", "/system"],
] as const;

export default function App() {
  const loc = useLocation();
  return (
    <div className="flex min-h-screen bg-[#0a0d12] text-slate-100">
      <aside className="w-48 shrink-0 border-r border-slate-800 bg-[#0d1118] p-3">
        <div className="px-2 pb-3 text-[15px] font-extrabold tracking-wide">
          REPURPOSE<span className="text-[#5f8dd3]">AI</span>
        </div>
        {NAV.map(([label, to]) => (
          <Link key={to} to={to}
            className={`block rounded-lg px-3 py-2 text-sm ${loc.pathname === to ? "bg-slate-800 text-white" : "text-slate-400 hover:bg-slate-800/60 hover:text-white"}`}>
            {label}
          </Link>
        ))}
      </aside>
      <main className="mx-auto w-full max-w-6xl flex-1 overflow-auto p-5 pb-16">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/review" element={<Review />} />
          <Route path="/exports" element={<Exports />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/system" element={<System />} />
        </Routes>
      </main>
    </div>
  );
}
