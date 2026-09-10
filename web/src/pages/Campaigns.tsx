import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Campaign, get, post } from "../api";

export default function Campaigns() {
  const [list, setList] = useState<Campaign[]>([]);
  const [name, setName] = useState("");
  const load = () => { get<{ items: Campaign[] }>("/api/campaigns").then((r) => setList(r.items)).catch(() => {}); };
  useEffect(() => { load(); }, []);
  const create = async () => {
    if (!name.trim()) return;
    await post("/api/campaigns", { name, rules: {}, verified: false });
    setName("");
    load();
  };
  return (
    <div>
      <h1 className="mb-4 text-xl font-bold">Campaigns</h1>
      <div className="mb-4 flex gap-2">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New campaign name"
          className="w-full rounded-lg border border-slate-700 bg-[#0a0d12] px-3 py-2 text-sm" />
        <button onClick={() => void create()} className="rounded-lg bg-[#2e5aa8] px-4 py-2 text-sm font-semibold text-white">Create</button>
      </div>
      {list.map((c) => (
        <div key={c.id} className="mb-2 flex items-center gap-2 rounded-xl border border-slate-800 bg-[#11151d] p-3 text-sm">
          <span className="font-medium">{c.name}</span>
          <span className="text-slate-500">v{c.version}</span>
          {c.ready
            ? <span className="rounded-full border border-emerald-800 px-2 py-0.5 text-xs text-emerald-300">READY</span>
            : <span className="rounded-full border border-red-800 px-2 py-0.5 text-xs text-red-300">BLOCKED {c.blockers.length}</span>}
          <span className="flex-1" />
          <Link className="text-[#5f8dd3]" to={`/campaign/${c.id}`}>Open</Link>
        </div>
      ))}
      {!list.length && <div className="text-sm text-slate-400">No campaigns. Create one for payout-gated clipping.</div>}
    </div>
  );
}
