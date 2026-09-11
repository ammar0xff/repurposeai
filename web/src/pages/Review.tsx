import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { clipVideoUrl, get, post, type ClipItem, type Project } from "../api";
import {
  Button,
  Chip,
  Dot,
  EmptyState,
  Field,
  PageHead,
  Panel,
  Progress,
} from "../components/ui";
import { CheckIcon, CopyIcon, ExportIcon, FilmIcon } from "../icons";
import { fmtTime } from "../lib/format";

const AXES = ["hook", "standalone", "payoff", "clarity", "emotion", "retention"];

const DECISION_META: Record<
  string,
  { label: string; key: string; cls: string }
> = {
  approved: { label: "Approve", key: "A", cls: "text-success border-success/40 hover:bg-success-tint" },
  rejected: { label: "Reject", key: "R", cls: "text-danger border-danger/40 hover:bg-danger-tint" },
  needs_edit: { label: "Needs edit", key: "E", cls: "text-warn border-warn/40 hover:bg-warn-tint" },
  exported: { label: "Exported", key: "X", cls: "text-muted border-line hover:bg-surface-2" },
};

function clipRange(c: ClipItem): string {
  return `${fmtTime(c.start)} to ${fmtTime(c.end)}`;
}

export default function Review() {
  const [params] = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [pid, setPid] = useState(params.get("project") || "");
  const [clips, setClips] = useState<ClipItem[]>([]);
  const [idx, setIdx] = useState(0);
  const [copied, setCopied] = useState<"title" | "caption" | null>(null);
  const video = useRef<HTMLVideoElement>(null);

  const [urls, setUrls] = useState<Record<string, string>>({});
  const inflight = useRef(new Set<string>());

  const ensureUrl = useCallback(
    (id: string) => {
      if (urls[id] || inflight.current.has(id)) return;
      inflight.current.add(id);
      clipVideoUrl(id)
        .then((u) => {
          setUrls((prev) => ({ ...prev, [id]: u }));
          inflight.current.delete(id);
        })
        .catch(() => inflight.current.delete(id));
    },
    [urls],
  );

  const loadProjects = useCallback(() => {
    void get<{ items: Project[] }>("/api/projects")
      .then((r) => {
        setProjects(r.items);
        if (!pid && r.items[0]) setPid(r.items[0].id);
      })
      .catch(() => {});
  }, [pid]);

  useEffect(loadProjects, [loadProjects]);

  useEffect(() => {
    if (!pid) return;
    void get<ClipItem[]>(`/api/projects/${pid}/clips`)
      .then((cs) => {
        setClips(cs);
        setIdx(0);
      })
      .catch(() => {});
  }, [pid]);

  const cur = clips[Math.min(idx, Math.max(0, clips.length - 1))];

  useEffect(() => {
    if (!clips.length) return;
    const lo = Math.max(0, idx - 4);
    const hi = Math.min(clips.length - 1, idx + 4);
    for (let i = lo; i <= hi; i += 1) ensureUrl(clips[i].id);
  }, [clips, idx, ensureUrl]);

  const decide = useCallback(
    async (d: string) => {
      if (!cur) return;
      try {
        await post(`/api/clips/${cur.id}/${d === "approved" ? "approve" : "reject"}`, {
          decision: d,
        });
        setClips((cs) => cs.map((c) => (c.id === cur.id ? { ...c, decision: d } : c)));
      } catch {
        /* keep decision untouched; user retries */
      }
    },
    [cur],
  );

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = (e.target as HTMLElement)?.tagName;
      if (/INPUT|TEXTAREA|SELECT/.test(t || "")) return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        setIdx((i) => Math.min(i + 1, clips.length - 1));
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === " ") {
        e.preventDefault();
        const v = video.current;
        if (v) (v.paused ? v.play() : v.pause());
      } else if (e.key.toLowerCase() === "a") {
        void decide("approved");
      } else if (e.key.toLowerCase() === "r") {
        void decide("rejected");
      } else if (e.key.toLowerCase() === "e") {
        void decide("needs_edit");
      } else if (e.key.toLowerCase() === "x") {
        void decide("exported");
      }
    };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [clips.length, decide]);

  const copyField = (kind: "title" | "caption") => {
    const el = document.getElementById(`rv-${kind}`) as HTMLInputElement | HTMLTextAreaElement | null;
    if (!el) return;
    el.select();
    void navigator.clipboard?.writeText(el.value);
    setCopied(kind);
    window.setTimeout(() => setCopied(null), 1400);
  };

  const decidedCount = useMemo(() => clips.filter((c) => c.decision).length, [clips]);
  const title = cur?.metadata.titles[cur.metadata.chosen_title] || cur?.metadata.titles[0] || "";

  const checkedValidation = cur?.validation?.checks ?? {};

  return (
    <div>
      <PageHead
        kicker="Review"
        title="Cuts"
        right={
          clips.length ? (
            <span className="mono text-xs text-faint">
              {decidedCount}/{clips.length} decided
            </span>
          ) : null
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="w-56">
          <select
            value={pid}
            onChange={(e) => setPid(e.target.value)}
            className="field cursor-pointer"
          >
            {!pid ? <option value="">Select a project</option> : null}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </div>
        <div className="hidden items-center gap-3 text-[11px] text-faint lg:flex">
          <span>
            <span className="kbd">←</span> <span className="kbd">→</span> move
          </span>
          <span>
            <span className="kbd">space</span> play
          </span>
          <span>decide with</span>
          {Object.values(DECISION_META).map((d) => (
            <span key={d.key} className="flex items-center gap-1">
              <span className="kbd">{d.key}</span>
              {d.label}
            </span>
          ))}
        </div>
      </div>

      {!cur ? (
        <Panel>
          <EmptyState
            icon={<FilmIcon size={26} />}
            title="No cuts here yet"
            copy="Put a video through the Studio and the ranked, captioned cuts will show up for review."
            action={
              <Link to="/">
                <Button variant="primary" size="sm">
                  Open the studio
                </Button>
              </Link>
            }
          />
        </Panel>
      ) : (
        <div className="grid items-start gap-5 lg:grid-cols-[1.35fr_1fr]">
          <div>
            <div className="panel relative overflow-hidden bg-black">
              <video
                key={cur.id}
                ref={video}
                controls
                playsInline
                preload="metadata"
                src={urls[cur.id] ?? ""}
                className="aspect-video w-full"
              />
            </div>

            <div className="mt-3 flex gap-2 overflow-x-auto pb-2">
              {clips.map((c, i) => {
                const active = i === idx;
                const u = urls[c.id];
                return (
                  <button
                    key={c.id}
                    onClick={() => setIdx(i)}
                    className={`relative h-16 w-28 shrink-0 overflow-hidden rounded-lg border text-left ${
                      active ? "border-primary" : "border-line hover:border-line-2"
                    }`}
                    aria-label={`Clip ${i + 1}`}
                  >
                    {u ? (
                      <video
                        src={u}
                        muted
                        playsInline
                        preload="metadata"
                        onLoadedMetadata={(e) => {
                          const v = e.currentTarget;
                          if (Number.isFinite(v.duration)) v.currentTime = Math.min(0.2, v.duration);
                        }}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="skeleton h-full w-full" />
                    )}
                    <span className="mono absolute bottom-1 left-1 rounded bg-black/70 px-1 text-[10px] text-white/80">
                      {i + 1} · {c.score.toFixed(1)} · {fmtTime(c.start)}
                    </span>
                    <span
                      className={`absolute right-1 top-1 h-2 w-2 rounded-full ${
                        active
                          ? "bg-primary"
                          : c.decision === "approved"
                            ? "bg-success"
                            : c.decision === "rejected"
                              ? "bg-danger"
                              : c.decision
                                ? "bg-warn"
                                : "bg-white/25"
                      }`}
                    />
                  </button>
                );
              })}
            </div>
          </div>

          <Panel className="lg:sticky lg:top-[84px]">
            <div className="mono mb-3 flex items-center justify-between text-[11px] text-faint">
              <span>
                CLIP {idx + 1}/{clips.length} · {clipRange(cur)} · {cur.render_profile}
              </span>
              <span className="flex items-center gap-1.5">
                {cur.decision ? (
                  <Chip
                    tone={
                      cur.decision === "approved"
                        ? "ok"
                        : cur.decision === "rejected"
                          ? "bad"
                          : "warn"
                    }
                  >
                    {cur.decision.replace("_", " ")}
                  </Chip>
                ) : (
                  <span>undecided</span>
                )}
              </span>
            </div>

            <div className="mb-1 flex items-baseline justify-between">
              <span className="mono text-xs text-faint">Score</span>
              <span className="mono text-2xl font-semibold text-primary">{cur.score.toFixed(1)}</span>
            </div>

            {Object.keys(cur.axes || {}).length ? (
              <div className="mb-4 mt-2 space-y-1.5">
                {AXES.filter((a) => a in (cur.axes || {})).map((a) => (
                  <div
                    key={a}
                    className="grid grid-cols-[96px_1fr_34px] items-center gap-2 text-xs"
                  >
                    <span className="capitalize text-muted">{a}</span>
                    <div className="h-1 overflow-hidden rounded-full bg-surface-3">
                      <Progress value={(cur.axes[a] || 0) * 10} />
                    </div>
                    <span className="mono text-right text-faint">{(cur.axes[a] || 0).toFixed(1)}</span>
                  </div>
                ))}
              </div>
            ) : null}

            {Object.keys(checkedValidation).length ? (
              <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-3 text-xs">
                {Object.entries(checkedValidation).map(([k, v]) => (
                  <span key={k} className="flex items-center gap-1.5 text-muted">
                    <Dot tone={v ? "ok" : "bad"} />
                    {k.replace(/_/g, " ")}
                    <span className={v ? "text-success" : "text-danger"}>{v ? "pass" : "FAIL"}</span>
                  </span>
                ))}
              </div>
            ) : null}

            <div className="space-y-3">
              <Field label="Posting title" hint={copied === "title" ? "copied" : "tap to copy"}>
                <div className="flex gap-2">
                  <input
                    id="rv-title"
                    readOnly
                    value={title}
                    className="field flex-1 cursor-default"
                  />
                  <Button variant="ghost" size="sm" onClick={() => copyField("title")} aria-label="Copy title">
                    <CopyIcon size={15} />
                  </Button>
                </div>
              </Field>
              <Field label="Caption" hint={copied === "caption" ? "copied" : "tap to copy"}>
                <div className="flex gap-2">
                  <textarea
                    id="rv-caption"
                    readOnly
                    value={cur.metadata.caption}
                    rows={3}
                    className="field flex-1 cursor-default resize-none"
                  />
                  <Button variant="ghost" size="sm" onClick={() => copyField("caption")} aria-label="Copy caption">
                    <CopyIcon size={15} />
                  </Button>
                </div>
              </Field>
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
                  Tags
                </span>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {(cur.metadata.hashtags || []).map((t) => (
                    <span key={t} className="rounded-full border border-line px-2 py-0.5 text-xs text-muted">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-2">
              {Object.entries(DECISION_META).map(([d, meta]) => (
                <button
                  key={d}
                  disabled={cur.decision === d}
                  onClick={() => void decide(d)}
                  className={`flex h-10 items-center justify-center gap-1.5 rounded-[10px] border text-[13px] font-semibold transition-colors duration-150 ease-out ${
                    cur.decision === d ? "bg-surface-2 opacity-60" : meta.cls
                  }`}
                >
                  {cur.decision === d ? <CheckIcon size={14} strokeWidth={2.4} /> : null}
                  {meta.label}
                  <span className="mono opacity-50">({meta.key})</span>
                </button>
              ))}
            </div>

            {urls[cur.id] ? (
              <a
                href={urls[cur.id]}
                download={`clip-${cur.id.slice(0, 8)}.mp4`}
                className="mt-2 flex items-center justify-center gap-1.5 text-xs text-faint underline decoration-dotted underline-offset-2 hover:text-muted"
              >
                <ExportIcon size={13} />
                Download this cut
              </a>
            ) : null}

            <p className="mt-3 border-t border-line pt-3 text-[11px] leading-relaxed text-faint">
              Generate is not publish. Approved cuts leave this app only via the export
              bundle in Library.
            </p>
          </Panel>
        </div>
      )}
    </div>
  );
}