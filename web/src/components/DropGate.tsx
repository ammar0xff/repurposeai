import { useRef, useState, type DragEvent } from "react";
import { post, uploadMedia, type Project } from "../api";
import { FilmIcon, PlayIcon, UploadIcon, XIcon } from "../icons";
import { fmtBytes, fmtTime, mediaError, titleStem } from "../lib/format";
import { Button } from "./ui";

export interface Started {
  projectId: string;
  jobId: string;
}

const CLIP_COUNT = 5;

export default function DropGate({ onStart }: { onStart: (s: Started) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [over, setOver] = useState(false);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [duration, setDuration] = useState<number | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const depth = useRef(0);

  const pick = (f?: File | null) => {
    if (!f) return;
    const e = mediaError(f.name);
    if (e) {
      setError(e);
      setFile(null);
      return;
    }
    setError("");
    setFile(f);
    setDuration(null);
    const url = URL.createObjectURL(f);
    const el =
      document.createElement(f.type.startsWith("audio") ? "audio" : "video");
    el.preload = "metadata";
    el.onloadedmetadata = () => setDuration(el.duration);
    el.src = url;
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    depth.current = 0;
    setOver(false);
    pick(e.dataTransfer.files?.[0]);
  };

  const openPicker = () => input.current?.click();

  const start = async () => {
    if (!file || starting) return;
    setStarting(true);
    setError("");
    try {
      const p = await post<Project>("/api/projects", {
        title: titleStem(file.name),
      });
      const up = await uploadMedia(p.id, file);
      const r = await post<{ job_id: string }>(`/api/projects/${p.id}/process`, {
        upload_key: up.storage_key,
        filename: file.name,
        params: { clip_count: CLIP_COUNT },
      });
      onStart({ projectId: p.id, jobId: r.job_id });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed. Try again.");
      setStarting(false);
    }
  };

  const clear = () => {
    setFile(null);
    setError("");
  };

  return (
    <div>
      <input
        ref={input}
        type="file"
        accept="video/*,audio/*,.mp4,.mkv,.mov,.webm,.avi,.m4a,.mp3,.wav"
        className="hidden"
        onChange={(e) => pick(e.target.files?.[0])}
      />

      {!file ? (
        <div
          role="button"
          tabIndex={0}
          aria-label="Upload a video"
          data-over={over ? "true" : "false"}
          onClick={openPicker}
          onKeyDown={(e) =>
            e.key === "Enter" || e.key === " " ? openPicker() : null
          }
          onDragEnter={(e) => {
            e.preventDefault();
            depth.current += 1;
            setOver(true);
          }}
          onDragOver={(e) => e.preventDefault()}
          onDragLeave={() => {
            depth.current = Math.max(0, depth.current - 1);
            if (depth.current === 0) setOver(false);
          }}
          onDrop={onDrop}
          className="filmgate relative cursor-pointer px-6 py-14 text-center sm:py-20"
        >
          <div className="pointer-events-none mx-auto flex max-w-md flex-col items-center gap-4">
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/15 text-primary">
              <UploadIcon size={24} strokeWidth={1.5} />
            </span>
            <div>
              <div className="text-lg font-semibold text-ink">
                Drop your long video here
              </div>
              <div className="mt-1.5 text-sm text-faint">
                or click to browse. RepurposeAI finds the moments worth keeping,
                ranks them, writes captions and renders cuts for review.
              </div>
            </div>
            <div className="mono text-[11px] uppercase tracking-[0.12em] text-faint">
              mp4 · mov · webm · mkv · m4a · mp3 · wav
            </div>
          </div>
        </div>
      ) : (
        <div className="filmgate p-4 sm:p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary">
              <PlayIcon size={22} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate font-semibold text-ink">{file.name}</div>
              <div className="mono mt-0.5 text-xs text-faint">
                {fmtBytes(file.size)}
                {duration ? ` · ${fmtTime(duration)}` : ""}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Button variant="primary" onClick={() => void start()} disabled={starting}>
                {starting ? "Starting the machine..." : "Transform into shorts"}
              </Button>
              <Button variant="ghost" size="md" onClick={clear} aria-label="Choose a different file">
                <XIcon size={16} />
                <span className="hidden sm:inline">Choose another</span>
              </Button>
            </div>
          </div>
        </div>
      )}

      {error ? (
        <div className="mt-3 flex items-start gap-2 rounded-[10px] border border-danger/40 bg-danger-tint px-3.5 py-2.5 text-sm text-danger">
          <FilmIcon size={15} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}
    </div>
  );
}