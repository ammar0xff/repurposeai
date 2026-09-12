import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  autofillSequence,
  clipVideoUrl,
  getSequence,
  get,
  putSequence,
  renderSequence,
  sequenceDownloadUrl,
  type ClipItem,
  type Project,
  type Sequence,
  type SequenceItem,
  type SequenceRender,
} from "../api";
import {
  Button,
  Chip,
  Dot,
  EmptyState,
  Field,
  Notice,
  PageHead,
  Panel,
  PanelTitle,
} from "../components/ui";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  AutoIcon,
  ExportIcon,
  FilmIcon,
  TrashIcon,
} from "../icons";
import { fmtTime } from "../lib/format";

const TRANSITION_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "Default" },
  { value: "crossfade", label: "Crossfade" },
  { value: "dissolve", label: "Dissolve" },
  { value: "zoom", label: "Zoom in" },
  { value: "slide_left", label: "Slide left" },
  { value: "slide_right", label: "Slide right" },
  { value: "slide_up", label: "Slide up" },
  { value: "slide_down", label: "Slide down" },
  { value: "wipe", label: "Wipe" },
  { value: "cut", label: "Hard cut" },
];

const TRANSITION_LABELS: Record<string, string> = Object.fromEntries(
  TRANSITION_OPTIONS.filter((t) => t.value).map((t) => [t.value, t.label]),
);

const REFRAME_OPTIONS: [value: string, label: string][] = [
  ["", "Default"],
  ["center", "Center"],
  ["smart", "Smart, follows faces"],
  ["face", "Face"],
  ["speaker", "Speaker"],
  ["manual", "Manual"],
];

const STYLE_OPTIONS: [value: string, label: string][] = [
  ["", "Default"],
  ["bold", "Bold"],
  ["clean", "Clean"],
  ["minimal", "Minimal"],
  ["podcast", "Podcast"],
  ["karaoke", "Karaoke"],
];

function transitionLabel(value: string | null | undefined): string {
  if (!value) return "default";
  return TRANSITION_LABELS[value] ?? value;
}

function rangeOf(it: SequenceItem): { start: number; end: number } {
  return {
    start: it.start ?? it.clip?.start ?? 0,
    end: it.end ?? it.clip?.end ?? 0,
  };
}

export default function Montage() {
  const [params] = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [pid, setPid] = useState(params.get("project") || "");
  const [clips, setClips] = useState<ClipItem[]>([]);
  const [items, setItems] = useState<SequenceItem[]>([]);
  const [dirty, setDirty] = useState(false);
  const [active, setActive] = useState(0);
  const [seqId, setSeqId] = useState("");
  const [validation, setValidation] = useState<Sequence["rendered_validation"]>({});
  const [renderResp, setRenderResp] = useState<SequenceRender | null>(null);
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [busy, setBusy] = useState<null | "save" | "autofill" | "render">(null);
  const [renderAt, setRenderAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [dlUrl, setDlUrl] = useState("");
  const inflight = useRef(new Set<string>());

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
    setItems([]);
    setDirty(false);
    setActive(0);
    setSeqId("");
    setValidation({});
    setRenderResp(null);
    setDlUrl("");
    setErr("");
    setNote("");
    setRenderAt(null);

    void get<ClipItem[]>(`/api/projects/${pid}/clips`)
      .then(setClips)
      .catch(() => setClips([]));

    void getSequence(pid)
      .then((s) => {
        setSeqId(s.id);
        setItems(s.items || []);
        setValidation(s.rendered_validation || {});
        if (s.rendered_key) {
          void sequenceDownloadUrl(pid)
            .then((u) =>
              setDlUrl((prev) => {
                if (prev) URL.revokeObjectURL(prev);
                return u;
              }),
            )
            .catch(() => {});
        }
      })
      .catch(() => {});
  }, [pid]);

  const ensureUrl = useCallback(
    (id: string) => {
      if (!id || urls[id] || inflight.current.has(id)) return;
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

  useEffect(() => {
    for (const it of items) ensureUrl(it.clip_id);
  }, [items, ensureUrl]);

  useEffect(() => {
    if (renderAt == null) return;
    const id = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - renderAt) / 1000)),
      1000,
    );
    return () => window.clearInterval(id);
  }, [renderAt]);

  useEffect(() => {
    return () => {
      if (dlUrl) URL.revokeObjectURL(dlUrl);
    };
  }, [dlUrl]);

  const clipById = useMemo(() => new Map(clips.map((c) => [c.id, c])), [clips]);
  const onStrip = useMemo(() => new Set(items.map((it) => it.clip_id)), [items]);
  const pool = useMemo(() => clips.filter((c) => !onStrip.has(c.id)), [clips, onStrip]);

  const estimate = useMemo(() => {
    let d = 0;
    items.forEach((it, i) => {
      const r = rangeOf(it);
      d += Math.max(0, r.end - r.start);
      if (i > 0) d -= it.transition_duration ?? 0.8;
    });
    return Math.max(0, d);
  }, [items]);

  const curIndex = items.length ? Math.min(active, items.length - 1) : -1;
  const cur = curIndex >= 0 ? items[curIndex] : null;
  const curMeta = cur ? clipById.get(cur.clip_id) : null;

  const setErrEmpty = () => setErr("");

  const updateItem = useCallback(
    (i: number, patch: Partial<SequenceItem>) => {
      setItems((prev) => prev.map((it, j) => (j === i ? { ...it, ...patch } : it)));
      setDirty(true);
    },
    [],
  );

  const move = useCallback(
    (from: number, to: number) => {
      if (from === to || busy) return;
      setItems((prev) => {
        const next = [...prev];
        const [m] = next.splice(from, 1);
        next.splice(to, 0, m);
        return next;
      });
      setActive(to);
      setDirty(true);
    },
    [busy],
  );

  const drop = useCallback(
    (to: number) => {
      if (dragFrom == null) return;
      move(dragFrom, Math.max(0, Math.min(to, items.length - 1)));
      setDragFrom(null);
    },
    [dragFrom, move, items.length],
  );

  const remove = useCallback(
    (i: number) => {
      if (busy) return;
      const next = items.filter((_, j) => j !== i);
      setItems(next);
      setActive(Math.max(0, Math.min(i, next.length - 1)));
      setDirty(true);
    },
    [items, busy],
  );

  const appendClip = useCallback(
    (cid: string) => {
      if (busy) return;
      setItems((prev) => [...prev, { clip_id: cid }]);
      setActive(items.length);
      setDirty(true);
    },
    [items.length, busy],
  );

  const saveSeq = useCallback(async () => {
    if (!pid || busy) return;
    setBusy("save");
    setErr("");
    try {
      const s = await putSequence(pid, { items });
      setSeqId(s.id);
      setValidation(s.rendered_validation || {});
      setDirty(false);
      setNote("Timeline saved");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save the timeline");
    } finally {
      setBusy(null);
    }
  }, [pid, items, busy]);

  const doAutofill = useCallback(async () => {
    if (!pid || busy) return;
    setBusy("autofill");
    setErr("");
    setNote("");
    try {
      const s = await autofillSequence(pid);
      setSeqId(s.id);
      setItems(s.items || []);
      setValidation(s.rendered_validation || {});
      setActive(0);
      setDirty(false);
      setNote("Composed from the best-ranked cuts");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Auto-fill found nothing to compose");
    } finally {
      setBusy(null);
    }
  }, [pid, busy]);

  const doRender = useCallback(async () => {
    if (!pid || busy || !items.length) return;
    setBusy("render");
    setErr("");
    setNote("");
    setRenderResp(null);
    setDlUrl("");
    setRenderAt(Date.now());
    setElapsed(0);
    try {
      if (dirty) await saveSeq();
      const resp = await renderSequence(pid, {
        transition: undefined,
        transition_duration: undefined,
      });
      setRenderResp(resp);
      setValidation(resp.validation || {});
      try {
        const u = await sequenceDownloadUrl(pid);
        setDlUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return u;
        });
      } catch {
        /* montage still listed in the footer even if fetch fails */
      }
    } catch (e) {
      setErr(
        e instanceof Error
          ? `Render failed: ${e.message}`
          : "Render failed. The stitch could not be completed.",
      );
    } finally {
      setRenderAt(null);
      setBusy(null);
    }
  }, [pid, items, dirty, busy, saveSeq]);

  const checks = validation.checks ?? {};
  const renderStatus = renderResp?.validation?.status ?? validation.status ?? "";

  return (
    <div>
      <PageHead
        kicker="Montage"
        title="Assemble the cut"
        right={
          <div className="flex items-center gap-2">
            {dirty ? (
              <Chip tone="warn">unsaved</Chip>
            ) : items.length ? (
              <span className="mono hidden text-[11px] text-faint sm:inline">
                {seqId ? `seq ${seqId.slice(0, 8)}` : "no sequence yet"}
              </span>
            ) : null}
            <Button
              variant="ghost"
              size="sm"
              disabled={busy != null || !items.length || !dirty}
              onClick={() => void saveSeq()}
            >
              {busy === "save" ? "Saving..." : "Save"}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={busy != null || !clips.length}
              onClick={() => void doAutofill()}
            >
              <AutoIcon size={15} />
              {busy === "autofill" ? "Composing..." : "Auto-fill"}
            </Button>
          </div>
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
        <div className="mono hidden items-center gap-2 text-[11px] text-faint lg:flex">
          {items.length ? <span>~{fmtTime(estimate)} output</span> : null}
          {items.length && validation.status ? (
            <span>
              <Dot tone={validation.status === "READY" ? "ok" : "bad"} />
              last render {validation.status.toLowerCase()}
            </span>
          ) : null}
        </div>
      </div>

      {!pid ? (
        <Panel>
          <EmptyState
            title="Choose a project to assemble"
            copy="Pick a project above, then arrange its rendered cuts into one montage."
          />
        </Panel>
      ) : (
        <div className="grid items-start gap-5 lg:grid-cols-[1.5fr_1fr]">
          <div>
            {dlUrl ? (
              <Panel className="mb-4">
                <PanelTitle hint="what the last stitch produced">
                  Preview
                </PanelTitle>
                {renderStatus ? (
                  <div className="mono mb-2 flex items-center gap-2 text-[11px] text-faint">
                    {renderResp?.duration != null ? (
                      <span>renders {fmtTime(renderResp.duration)}</span>
                    ) : null}
                    <span className="flex items-center gap-1.5">
                      <Dot tone={renderStatus === "READY" ? "ok" : "bad"} />
                      {renderStatus.toLowerCase()}
                    </span>
                  </div>
                ) : null}
                <div className="flex justify-center">
                  <video
                    src={dlUrl}
                    controls
                    playsInline
                    preload="metadata"
                    className="aspect-[9/16] w-44 rounded-lg border border-line bg-black"
                  />
                </div>
              </Panel>
            ) : null}
            <Panel>
              <PanelTitle hint={items.length ? "drag to reorder" : ""}>
                Cut strip
              </PanelTitle>
              {items.length ? (
                <div className="-mx-1 flex items-stretch gap-0 overflow-x-auto px-1 pb-2">
                  {items.map((it, i) => {
                    const meta = clipById.get(it.clip_id);
                    const r = rangeOf(it);
                    const activeCard = i === curIndex;
                    return (
                      <Fragment key={`${it.clip_id}-${i}`}>
                        {i > 0 ? (
                          <div className="flex shrink-0 flex-col justify-center px-1">
                            <button
                              onClick={() => setActive(i)}
                              title={`Transition into cut ${i + 1}`}
                              className="flex flex-col items-center gap-0.5 rounded-full border border-line bg-surface-2 px-2 py-1 text-[9px] text-faint transition-colors duration-150 hover:border-primary/50 hover:text-body"
                            >
                              <span className="mono uppercase tracking-wide">
                                {transitionLabel(it.transition)}
                              </span>
                              <span className="mono">{it.transition_duration ?? 0.8}s</span>
                            </button>
                          </div>
                        ) : null}
                        <button
                          draggable={busy !== "render"}
                          onDragStart={() => setDragFrom(i)}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={() => drop(i)}
                          onDragEnd={() => setDragFrom(null)}
                          onClick={() => setActive(i)}
                          aria-label={`Cut ${i + 1}, score ${meta ? meta.score.toFixed(1) : "unknown"}`}
                          className={`relative h-44 w-24 shrink-0 cursor-grab overflow-hidden rounded-[10px] border text-left transition-colors duration-150 ${
                            activeCard ? "border-primary" : "border-line hover:border-line-2"
                          }`}
                        >
                          {urls[it.clip_id] ? (
                            <video
                              src={urls[it.clip_id]}
                              muted
                              playsInline
                              preload="metadata"
                              onLoadedMetadata={(e) => {
                                const v = e.currentTarget;
                                if (Number.isFinite(v.duration))
                                  v.currentTime = Math.min(0.2, v.duration);
                              }}
                              className="h-full w-full object-cover"
                            />
                          ) : (
                            <div className="skeleton h-full w-full" />
                          )}
                          <span className="absolute left-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded bg-black/70 text-[10px] text-white/80">
                            {i + 1}
                          </span>
                          <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 to-transparent px-1.5 pb-1 pt-3">
                            <span className="mono block text-[9px] leading-tight text-white/80">
                              {meta ? meta.score.toFixed(1) : "--"} · {fmtTime(r.start)}
                            </span>
                            <span className="mono block text-[9px] leading-tight text-white/60">
                              {fmtTime(r.end - r.start)}
                            </span>
                          </span>
                        </button>
                      </Fragment>
                    );
                  })}
                  <button
                    disabled={busy != null || !pool.length}
                    onClick={() => {
                      const nxt = pool[0];
                      if (nxt) appendClip(nxt.id);
                    }}
                    aria-label="Add the next cut from the shelf"
                    className="flex h-44 w-16 shrink-0 flex-col items-center justify-center gap-1 rounded-[10px] border border-dashed border-line text-faint transition-colors duration-150 hover:border-primary/50 hover:text-body disabled:opacity-40"
                  >
                    <span className="text-xl leading-none">+</span>
                    <span className="text-[10px] uppercase tracking-[0.12em]">Add</span>
                  </button>
                </div>
              ) : (
                <EmptyState
                  icon={<FilmIcon size={26} />}
                  title="The strip is empty"
                  copy={
                    clips.length
                      ? "Pull rendered cuts onto it, one clip at a time, or let the machine compose from its best-rated cuts."
                      : "This project has no rendered cuts yet. Run it through the Studio first."
                  }
                  action={
                    clips.length ? (
                      <Button
                        variant="primary"
                        size="sm"
                        disabled={busy != null}
                        onClick={() => void doAutofill()}
                      >
                        <AutoIcon size={15} />
                        Auto-fill from best cuts
                      </Button>
                    ) : (
                      <Link to="/">
                        <Button variant="ghost" size="sm">
                          Go to the studio
                        </Button>
                      </Link>
                    )
                  }
                />
              )}
            </Panel>

            <Panel className="mt-4">
              <PanelTitle hint={pool.length ? `${pool.length} left` : ""}>
                From the cut shelf
              </PanelTitle>
              {pool.length ? (
                <div className="flex flex-wrap gap-2">
                  {pool.map((c) => (
                    <button
                      key={c.id}
                      disabled={busy != null}
                      onClick={() => appendClip(c.id)}
                      className="flex items-center gap-2 rounded-[10px] border border-line px-2.5 py-1.5 text-xs text-muted transition-colors duration-150 hover:border-primary/50 hover:text-body disabled:opacity-40"
                    >
                      <FilmIcon size={14} className="text-faint" />
                      <span className="mono">{c.score.toFixed(1)}</span>
                      <span>{fmtTime(c.start)}</span>
                      <span className="text-faint">+</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-xs leading-relaxed text-faint">
                  Every rendered cut is on the strip. Run long-form material through the
                  Studio for more.
                </div>
              )}
            </Panel>
          </div>

          <Panel className="lg:sticky lg:top-[84px]">
            {cur && curMeta ? (
              <>
                <div className="mono mb-3 flex items-center justify-between text-[11px] text-faint">
                  <span>
                    CUT {curIndex + 1}/{items.length} · {curMeta.render_profile}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Dot tone="idle" />
                    score {curMeta.score.toFixed(1)}
                  </span>
                </div>

                <div className="mb-4 flex justify-center">
                  <video
                    key={cur.clip_id}
                    src={urls[cur.clip_id] ?? ""}
                    controls
                    playsInline
                    preload="metadata"
                    className="aspect-[9/16] w-28 rounded-lg border border-line bg-black"
                  />
                </div>

                <div className="space-y-3">
                  {curIndex > 0 ? (
                    <div className="grid grid-cols-[1fr_110px] gap-2">
                      <Field label="Into this cut">
                        <select
                          value={cur.transition ?? ""}
                          onChange={(e) =>
                            updateItem(curIndex, {
                              transition: e.target.value || null,
                            })
                          }
                          className="field cursor-pointer"
                        >
                          {TRANSITION_OPTIONS.map((t) => (
                            <option key={t.value} value={t.value}>
                              {t.label}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <Field label="Seconds" hint="0.1 to 2.0">
                        <input
                          type="number"
                          min={0.1}
                          max={2}
                          step={0.1}
                          value={cur.transition_duration ?? 0.8}
                          onChange={(e) => {
                            const v = Number(e.target.value);
                            updateItem(curIndex, {
                              transition_duration: Number.isFinite(v) && v > 0 ? v : null,
                            });
                          }}
                          className="field"
                        />
                      </Field>
                    </div>
                  ) : (
                    <div className="mb-3 border-t border-line pt-3 text-xs text-faint">
                      This cut opens the montage. No transition before it.
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2">
                    <Field
                      label="Start in source"
                      hint={curMeta ? fmtTime(curMeta.start) : ""}
                    >
                      <input
                        type="number"
                        min={0}
                        step={0.1}
                        value={Number(rangeOf(cur).start.toFixed(1))}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          updateItem(curIndex, {
                            start: Number.isFinite(v) ? v : null,
                          });
                        }}
                        className="field"
                      />
                    </Field>
                    <Field label="End in source" hint={curMeta ? fmtTime(curMeta.end) : ""}>
                      <input
                        type="number"
                        min={0}
                        step={0.1}
                        value={Number(rangeOf(cur).end.toFixed(1))}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          updateItem(curIndex, {
                            end: Number.isFinite(v) ? v : null,
                          });
                        }}
                        className="field"
                      />
                    </Field>
                  </div>

                  <Field label="Frame">
                    <select
                      value={cur.reframe ?? ""}
                      onChange={(e) => updateItem(curIndex, { reframe: e.target.value || null })}
                      className="field cursor-pointer"
                    >
                      {REFRAME_OPTIONS.map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Caption style">
                    <select
                      value={cur.caption_style ?? ""}
                      onChange={(e) =>
                        updateItem(curIndex, { caption_style: e.target.value || null })
                      }
                      className="field cursor-pointer"
                    >
                      {STYLE_OPTIONS.map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Credit" hint="bottom line">
                    <input
                      type="text"
                      placeholder="optional @handle"
                      value={cur.credit ?? ""}
                      onChange={(e) =>
                        updateItem(curIndex, { credit: e.target.value || null })
                      }
                      className="field"
                    />
                  </Field>
                </div>

                <div className="mt-4 flex items-center gap-2">
                  <Button
                    size="sm"
                    disabled={busy != null || curIndex === 0}
                    onClick={() => move(curIndex, curIndex - 1)}
                    aria-label="Move cut earlier"
                  >
                    <ArrowLeftIcon size={14} />
                    Earlier
                  </Button>
                  <Button
                    size="sm"
                    disabled={busy != null || curIndex === items.length - 1}
                    onClick={() => move(curIndex, curIndex + 1)}
                    aria-label="Move cut later"
                  >
                    Later
                    <ArrowRightIcon size={14} />
                  </Button>
                  <span className="flex-1" />
                  <Button
                    size="sm"
                    variant="danger"
                    disabled={busy != null}
                    onClick={() => remove(curIndex)}
                    aria-label="Remove cut from strip"
                  >
                    <TrashIcon size={14} />
                    Drop
                  </Button>
                </div>
              </>
            ) : (
              <EmptyState
                icon={<FilmIcon size={26} />}
                title="No cut selected"
                copy="Pick a cut on the strip to trim, frame, caption and credit it."
              />
            )}
          </Panel>
        </div>
      )}

      {pid ? (
        <Panel className="mt-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-ink">Stitch the montage</div>
              <div className="mt-0.5 text-xs leading-relaxed text-faint">
                {items.length
                  ? `${items.length} cuts, about ${fmtTime(estimate)} of output. The stitch runs on this machine and can take a couple minutes for five cuts.`
                  : "Add cuts to the strip first."}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {renderResp?.validation?.status ? (
                <Chip tone={renderResp.validation.status === "READY" ? "ok" : "bad"}>
                  {renderResp.validation.status.toLowerCase()}
                </Chip>
              ) : null}
              {busy === "render" ? (
                <span className="mono inline-flex items-center gap-1.5 text-xs text-primary">
                  <span className="inline-block h-1.5 w-1.5 animate-pulse-soft rounded-full bg-primary" />
                  {fmtTime(elapsed)} elapsed, stitching
                </span>
              ) : null}
              <Button
                variant="primary"
                size="md"
                disabled={busy != null || !items.length}
                onClick={() => void doRender()}
              >
                {busy === "render"
                  ? "Rendering..."
                  : dirty
                    ? "Save and render"
                    : "Render montage"}
              </Button>
              {dlUrl ? (
                <a
                  href={dlUrl}
                  download={`montage-${seqId.slice(0, 8)}.mp4`}
                  className="btn-ghost inline-flex min-h-[42px] items-center justify-center gap-2 rounded-full px-4 text-sm font-semibold"
                >
                  <ExportIcon size={15} />
                  Download
                </a>
              ) : null}
            </div>
          </div>

          {Object.keys(checks).length ? (
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-3 text-xs">
              {Object.entries(checks).map(([k, v]) => (
                <span key={k} className="flex items-center gap-1.5 text-muted">
                  <Dot tone={v ? "ok" : "bad"} />
                  {k.replace(/_/g, " ")}
                  <span className={v ? "text-success" : "text-danger"}>
                    {v ? "pass" : "fail"}
                  </span>
                </span>
              ))}
            </div>
          ) : null}

          {err ? (
            <div className="mt-3">
              <Notice tone="bad" onClose={setErrEmpty}>
                {err}
              </Notice>
            </div>
          ) : null}
          {note ? (
            <div className="mt-3">
              <Notice tone="ok" onClose={() => setNote("")}>
                {note}
              </Notice>
            </div>
          ) : null}
        </Panel>
      ) : null}
    </div>
  );
}