import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Campaign, get, post, Project, put } from "../api";
import {
  Button,
  Chip,
  Field,
  Input,
  Notice,
  PageHead,
  Panel,
  PanelTitle,
  Textarea,
} from "../components/ui";
import { CampaignIcon } from "../icons";
import type { NoticeTone } from "../components/ui";

export default function CampaignDetail() {
  const { id } = useParams();
  const [c, setC] = useState<Campaign | null>(null);
  const [json, setJson] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [pid, setPid] = useState("");
  const [source, setSource] = useState("");
  const [dry, setDry] = useState(true);
  const [note, setNote] = useState<{ tone: NoticeTone; msg: string } | null>(null);

  const load = () => {
    if (!id) return;
    void get<Campaign>(`/api/campaigns/${id}`)
      .then((x) => {
        setC(x);
        setJson(JSON.stringify(x.rules, null, 2));
      })
      .catch(() => {});
  };

  useEffect(load, [id]);

  useEffect(() => {
    void get<{ items: Project[] }>("/api/projects")
      .then((r) => {
        setProjects(r.items);
        if (!pid && r.items[0]) setPid(r.items[0].id);
      })
      .catch(() => {});
  }, [pid]);

  if (!c) {
    return <div className="text-sm text-faint">Loading brief...</div>;
  }

  const r = (c.rules || {}) as Record<string, unknown>;
  const dur = (r.duration || {}) as Record<string, unknown>;
  const credit = (r.credit || {}) as Record<string, unknown>;

  const save = async () => {
    let rules: Record<string, unknown> = {};
    try {
      rules = JSON.parse(json);
    } catch {
      setNote({ tone: "bad", msg: "Brief JSON is not valid. Fix it before saving." });
      return;
    }
    try {
      await put(`/api/campaigns/${c.id}`, { name: c.name, rules, verified: c.verified });
      setNote({ tone: "ok", msg: "Brief saved." });
      load();
    } catch (e) {
      setNote({ tone: "bad", msg: e instanceof Error ? e.message : "Save failed." });
    }
  };

  const verify = async (v: boolean) => {
    let rules: Record<string, unknown> = {};
    try {
      rules = JSON.parse(json);
    } catch {
      setNote({ tone: "bad", msg: "Fix the JSON before marking the brief verified." });
      return;
    }
    try {
      await put(`/api/campaigns/${c.id}`, { name: c.name, rules, verified: v });
      load();
    } catch (e) {
      setNote({ tone: "bad", msg: e instanceof Error ? e.message : "Verification failed." });
    }
  };

  const generate = async () => {
    if (!pid || !source.trim()) {
      setNote({ tone: "warn", msg: "Pick a project and a source first." });
      return;
    }
    try {
      await post(`/api/projects/${pid}/process`, {
        source: source.trim(),
        params: { campaign_id: c.id, no_strict: dry, clip_count: 3 },
      });
      setNote({
        tone: dry ? "info" : "ok",
        msg: dry
          ? "Dry-run job started. It will never be submitted; check the jobs page for what it would approve."
          : "Production job started. Approved clips still leave this app only via export.",
      });
    } catch (e) {
      setNote({ tone: "bad", msg: e instanceof Error ? e.message : "Job did not start." });
    }
  };

  const sources = Array.isArray(r.sources) ? r.sources : [];

  return (
    <div>
      <PageHead
        kicker="Campaign"
        title={<span className="flex items-center gap-3">{c.name}</span>}
        right={
          <Chip tone={c.ready ? "ok" : "bad"}>
            {c.ready ? "ready" : `blocked ${c.blockers.length}`}
          </Chip>
        }
      />

      {note ? (
        <div className="mb-4">
          <Notice tone={note.tone} onClose={() => setNote(null)}>
            {note.msg}
          </Notice>
        </div>
      ) : null}

      {!c.ready ? (
        <div className="mb-4 rounded-[10px] border border-danger/40 bg-danger-tint p-4">
          <div className="text-sm font-semibold text-danger">
            {c.blockers.length} blocker{c.blockers.length === 1 ? "" : "s"} (production refused)
          </div>
          <ul className="mt-1.5 space-y-1">
            {c.blockers.map((b) => (
              <li key={b} className="flex items-center gap-2 text-sm text-body">
                <span className="h-1.5 w-1.5 rounded-full bg-danger" />
                {b}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid items-start gap-5 lg:grid-cols-2">
        <Panel>
          <PanelTitle>Policy</PanelTitle>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <div className="flex justify-between border-b border-line pb-1.5">
              <span className="text-faint">Rate</span>
              <span className="mono text-body">{String(r.rate_per_1k ?? "-")}/1k</span>
            </div>
            <div className="flex justify-between border-b border-line pb-1.5">
              <span className="text-faint">Budget</span>
              <span className="mono text-body">{String(r.budget ?? "-")}</span>
            </div>
            <div className="flex justify-between border-b border-line pb-1.5">
              <span className="text-faint">Duration</span>
              <span className="mono text-body">
                {String(dur.min ?? "-")}s to {String(dur.max ?? "-")}s
              </span>
            </div>
            <div className="flex justify-between border-b border-line pb-1.5">
              <span className="text-faint">Cap</span>
              <span className="mono text-body">{String(r.cap ?? "-")}</span>
            </div>
          </div>
          <div className="mt-3 text-xs text-faint">
            Credit: <span className="text-muted">{String(credit.text ?? "-")}</span>
          </div>
        </Panel>

        <Panel>
          <PanelTitle>Sources and tags</PanelTitle>
          <div className="space-y-1.5">
            {sources.length ? (
              sources.map((s) => (
                <div key={String(s)} className="flex items-center gap-2 text-sm text-body">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" />
                  {String(s)}
                </div>
              ))
            ) : (
              <div className="text-sm text-faint">No sources listed yet.</div>
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {(Array.isArray(r.hashtags) ? r.hashtags : []).map((t) => (
              <span
                key={String(t)}
                className="rounded-full border border-line px-2 py-0.5 text-xs text-muted"
              >
                {String(t)}
              </span>
            ))}
          </div>
          <div className="mt-3 border-t border-line pt-3 text-[11px] text-faint">
            Generate is not submit. Posting stays manual, always.
          </div>
        </Panel>
      </div>

      <Panel className="mt-5">
        <PanelTitle>Generate (campaign-gated)</PanelTitle>
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            value={pid}
            onChange={(e) => setPid(e.target.value)}
            className="field w-full cursor-pointer sm:w-52"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
          <Input
            value={source}
            onChange={(e) => setSource(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void generate()}
            placeholder="Source file or URL"
          />
          <label className="flex shrink-0 cursor-pointer items-center gap-2 px-1 text-xs text-muted">
            <input
              type="checkbox"
              checked={dry}
              onChange={(e) => setDry(e.target.checked)}
              className="h-4 w-4"
            />
            dry-run only
          </label>
          <Button variant="primary" onClick={() => void generate()}>
            Generate
          </Button>
        </div>
      </Panel>

      <Panel className="mt-5">
        <PanelTitle hint="source of truth">Brief JSON</PanelTitle>
        <Textarea
          value={json}
          onChange={(e) => setJson(e.target.value)}
          rows={14}
          className="font-mono text-xs"
        />
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="primary" size="sm" onClick={() => void save()}>
            Save brief
          </Button>
          {!c.verified ? (
            <Button variant="ghost" size="sm" onClick={() => void verify(true)}>
              Mark verified
            </Button>
          ) : (
            <Button variant="danger" size="sm" onClick={() => void verify(false)}>
              Unverify
            </Button>
          )}
        </div>
      </Panel>
    </div>
  );
}