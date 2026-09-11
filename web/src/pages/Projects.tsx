import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { del, get, post, type Project } from "../api";
import {
  Button,
  Chip,
  EmptyState,
  Notice,
  PageHead,
  Panel,
} from "../components/ui";
import { ExportIcon, FilmIcon, ReviewIcon, TrashIcon } from "../icons";
import { fmtTime, timeAgo } from "../lib/format";
import type { NoticeTone } from "../components/ui";

export default function Projects() {
  const [list, setList] = useState<Project[]>([]);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<{ tone: NoticeTone; msg: string } | null>(null);

  const load = () =>
    void get<{ items: Project[] }>("/api/projects")
      .then((r) => setList(r.items))
      .catch(() => setNote({ tone: "bad", msg: "Could not load projects." }));

  useEffect(load, []);

  const exportBundle = async (p: Project) => {
    setBusy(p.id);
    try {
      const e = await post<{ manifest: { clips: unknown[] } }>(`/api/projects/${p.id}/export`);
      const n = (e.manifest?.clips ?? []).length;
      setNote({
        tone: "ok",
        msg: `Bundled ${n} clip${n === 1 ? "" : "s"} for "${p.title}". Approved cuts only travel in an export.`,
      });
    } catch (err) {
      setNote({ tone: "bad", msg: err instanceof Error ? err.message : "Export failed." });
    } finally {
      setBusy(null);
    }
  };

  const remove = async (p: Project) => {
    if (confirming !== p.id) {
      setConfirming(p.id);
      return;
    }
    setConfirming(null);
    try {
      await del(`/api/projects/${p.id}`);
      setList((l) => l.filter((x) => x.id !== p.id));
    } catch (err) {
      setNote({ tone: "bad", msg: err instanceof Error ? err.message : "Delete failed." });
    }
  };

  return (
    <div>
      <PageHead
        kicker="Library"
        title="Projects"
        right={
          list.length ? (
            <span className="mono text-xs text-faint">{list.length} on the shelf</span>
          ) : null
        }
      />

      {note ? (
        <div className="mb-4">
          <Notice tone={note.tone} onClose={() => setNote(null)}>
            {note.msg}
          </Notice>
        </div>
      ) : null}

      {list.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((p) => (
            <div key={p.id} className="panel overflow-hidden">
              <Link
                to={`/review?project=${p.id}`}
                className="group relative flex aspect-video items-center justify-center bg-gradient-to-br from-primary-tint via-surface-2 to-surface-3"
              >
                <FilmIcon
                  size={32}
                  className="text-primary/70 transition-transform duration-200 ease-out group-hover:scale-105"
                />
                <span className="absolute right-2.5 top-2.5">
                  <Chip tone={p.status === "processing" ? "warn" : "neutral"}>
                    {p.status}
                  </Chip>
                </span>
              </Link>
              <div className="p-4">
                <div className="truncate font-semibold text-ink">{p.title}</div>
                <div className="mono mt-1 text-[11px] text-faint">
                  {p.duration ? fmtTime(p.duration) : "no duration"} · {timeAgo(p.updated_at)}
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Link to={`/review?project=${p.id}`} className="flex-1">
                    <Button variant="primary" size="sm" className="w-full">
                      <ReviewIcon size={15} />
                      Review
                    </Button>
                  </Link>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void exportBundle(p)}
                    disabled={busy === p.id}
                    aria-label="Export bundle"
                  >
                    <ExportIcon size={15} />
                  </Button>
                  <Button
                    variant={confirming === p.id ? "danger" : "ghost"}
                    size="sm"
                    onClick={() => void remove(p)}
                    aria-label="Delete project"
                  >
                    {confirming === p.id ? <TrashIcon size={15} /> : <TrashIcon size={15} />}
                    {confirming === p.id ? "Sure?" : ""}
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Panel>
          <EmptyState
            icon={<FilmIcon size={26} />}
            title="The shelf is empty"
            copy="Drop a long video in the Studio and it will land here as a project with ranked, captioned cuts."
            action={
              <Link to="/">
                <Button variant="primary" size="sm">
                  Open the studio
                </Button>
              </Link>
            }
          />
        </Panel>
      )}
    </div>
  );
}