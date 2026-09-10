import { useEffect, useState } from "react";
import { get, Job, post } from "../api";

export default function Jobs() {
  const [list, setList] = useState<Job[]>([]);
  const load = () => get<Job[]>("/api/jobs").then(setList).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, []);
  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">Jobs</h1>
      {list.map((j) => (
        <div key={j.id} className="mb-2 rounded-xl border border-slate-800 bg-[#11151d] p-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-mono">{j.id.slice(0, 8)}</span>
            <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs">{j.status}{j.current_stage ? `, ${j.current_stage}` : ""}</span>
            <span className="tabular-nums text-slate-400">{j.progress}%</span>
            <span className="flex-1" />
            {(j.status === "running" || j.status === "queued") && (
              <button onClick={async () => { await post(`/api/jobs/${j.id}/cancel`); load(); }}
                className="rounded-lg border border-slate-700 px-3 py-1 text-xs">Cancel</button>
            )}
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded bg-slate-800">
            <div className="h-full bg-[#5f8dd3]" style={{ width: `${j.progress}%` }} /></div>
          {j.error && <div className="mt-1 text-xs text-red-400">{j.error}</div>}
        </div>
      ))}
      {!list.length && <div className="text-sm text-slate-400">No jobs.</div>}
    </div>
  );
}
