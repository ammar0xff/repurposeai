import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Campaign, get, post, Project, put } from "../api";

export default function CampaignDetail() {
  const { id } = useParams();
  const [c, setC] = useState<Campaign | null>(null);
  const [json, setJson] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [pid, setPid] = useState("");
  const [source, setSource] = useState("");
  const [dry, setDry] = useState(true);
  const load = () => {
    if (!id) return;
    get<Campaign>(`/api/campaigns/${id}`).then((x) => { setC(x); setJson(JSON.stringify(x.rules, null, 2)); }).catch(() => {});
  };
  useEffect(load, [id]);
  useEffect(() => { get<{ items: Project[] }>("/api/projects").then((r) => { setProjects(r.items); if (!pid && r.items[0]) setPid(r.items[0].id); }).catch(() => {}); }, [pid]);
  if (!c) return <div className="text-sm text-slate-400">Loading.</div>;
  const r = (c.rules || {}) as Record<string, unknown>;
  const dur = (r.duration || {}) as Record<string, unknown>;
  const credit = (r.credit || {}) as Record<string, unknown>;
  const save = async () => {
    let rules: Record<string, unknown> = {};
    try { rules = JSON.parse(json); } catch { alert("Invalid JSON"); return; }
    await put(`/api/campaigns/${c.id}`, { name: c.name, rules, verified: c.verified });
    load();
  };
  const verify = async (v: boolean) => {
    await put(`/api/campaigns/${c.id}`, { name: c.name, rules: JSON.parse(json), verified: v });
    load();
  };
  const generate = async () => {
    if (!pid || !source.trim()) { alert("Pick a project and a source"); return; }
    await post(`/api/projects/${pid}/process`,
      { source: source.trim(), params: { campaign_id: c.id, no_strict: dry, clip_count: 3 } });
    alert(dry ? "Dry-run job started (never submit)." : "Production job started.");
  };
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h1 className="text-xl font-bold">{c.name}</h1>
        {c.ready
          ? <span className="rounded-full border border-emerald-800 px-2 py-0.5 text-xs text-emerald-300">READY</span>
          : <span className="rounded-full border border-red-800 px-2 py-0.5 text-xs text-red-300">BLOCKED</span>}
      </div>
      {!c.ready && (
        <div className="mb-3 rounded-xl border border-red-900 bg-[#11151d] p-4">
          <h2 className="mb-1 text-sm font-semibold">{c.blockers.length} blockers (production refused)</h2>
          {c.blockers.map((b) => <div key={b} className="py-0.5 text-sm text-slate-300"><span className="mr-2 inline-block h-2 w-2 rounded-full bg-red-400" />{b}</div>)}
        </div>
      )}
      <div className="mb-3 grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-[#11151d] p-4 text-sm">
          <h2 className="mb-2 text-sm font-semibold">Policy</h2>
          <div>Rate: <b>{String(r.rate_per_1k ?? "-")}/1k</b></div>
          <div>Budget: <b>{String(r.budget ?? "-")}</b></div>
          <div>Duration: <b>{String(dur.min ?? "-")}s to {String(dur.max ?? "-")}s</b></div>
          <div>Credit: <b>{String(credit.text ?? "-")}</b></div>
          <div>Cap: <b>{String(r.cap ?? "-")}</b></div>
        </div>
        <div className="rounded-xl border border-slate-800 bg-[#11151d] p-4 text-sm">
          <h2 className="mb-2 text-sm font-semibold">Sources and tags</h2>
          {(Array.isArray(r.sources) ? r.sources : []).map((s) => <div key={String(s)}><span className="mr-2 inline-block h-2 w-2 rounded-full bg-emerald-400" />{String(s)}</div>)}
          <div className="mt-2">Tags: <b>{(Array.isArray(r.hashtags) ? r.hashtags : []).join(" ")}</b></div>
          <div className="mt-2 text-slate-500">Generate clips is not Submit. Posting stays manual.</div>
        </div>
      </div>
      <div className="mb-3 rounded-xl border border-slate-800 bg-[#11151d] p-4">
        <h2 className="mb-2 text-sm font-semibold">Generate (campaign-gated)</h2>
        <div className="flex flex-col gap-2 md:flex-row">
          <select value={pid} onChange={(e) => setPid(e.target.value)}
            className="rounded-lg border border-slate-700 bg-[#0a0d12] px-2 py-2 text-sm">
            {projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
          </select>
          <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source file or URL"
            className="w-full rounded-lg border border-slate-700 bg-[#0a0d12] px-3 py-2 text-sm" />
          <label className="flex items-center gap-1 text-xs text-slate-400">
            <input type="checkbox" checked={dry} onChange={(e) => setDry(e.target.checked)} /> dry-run
          </label>
          <button onClick={() => void generate()} className="rounded-lg bg-[#2e5aa8] px-4 py-2 text-sm font-semibold text-white">Generate</button>
        </div>
      </div>
      <div className="rounded-xl border border-slate-800 bg-[#11151d] p-4">
        <h2 className="mb-2 text-sm font-semibold">Brief JSON (source of truth)</h2>
        <textarea value={json} onChange={(e) => setJson(e.target.value)} rows={14}
          className="w-full rounded-lg border border-slate-700 bg-[#0a0d12] p-2 font-mono text-xs" />
        <div className="mt-2 flex gap-2">
          <button onClick={() => void save()} className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm">Save brief</button>
          {!c.verified
            ? <button onClick={() => void verify(true)} className="rounded-lg border border-emerald-800 px-3 py-1.5 text-sm text-emerald-300">Mark verified</button>
            : <button onClick={() => void verify(false)} className="rounded-lg border border-red-800 px-3 py-1.5 text-sm text-red-300">Unverify</button>}
        </div>
      </div>
    </div>
  );
}
