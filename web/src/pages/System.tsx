import { useEffect, useState } from "react";
import { get } from "../api";

export default function System() {
  const [h, setH] = useState<Record<string, { status: string; [k: string]: unknown }> | null>(null);
  const [p, setP] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    get<{ checks: typeof h }>("/api/system/readiness").then((r) => setH(r.checks)).catch(() => {});
    get<Record<string, unknown>>("/api/system/providers").then(setP).catch(() => {});
  }, []);
  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">System</h1>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-[#11151d] p-4">
          <h2 className="mb-2 text-sm font-semibold">Readiness</h2>
          {h ? Object.entries(h).map(([k, v]) => (
            <div key={k} className="flex justify-between py-1 text-sm">
              <span>{k}</span>
              <span className={v.status === "ok" ? "text-emerald-300" : "text-red-300"}>{v.status}</span>
            </div>
          )) : <div className="text-sm text-slate-400">Loading.</div>}
        </div>
        <div className="rounded-xl border border-slate-800 bg-[#11151d] p-4">
          <h2 className="mb-2 text-sm font-semibold">Providers</h2>
          <pre className="overflow-auto text-xs text-slate-400">{JSON.stringify(p, null, 1) || "Loading."}</pre>
        </div>
      </div>
    </div>
  );
}
