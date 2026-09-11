import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  TextareaHTMLAttributes,
} from "react";
import { XIcon } from "../icons";

type ButtonVariant = "primary" | "ghost" | "danger";
type ButtonSize = "sm" | "md";

export function Button({
  variant = "ghost",
  size = "md",
  className = "",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
}) {
  const sizeCls =
    size === "sm" ? "min-h-[34px] px-3.5 text-[13px]" : "min-h-[42px] px-5 text-sm";
  const variantCls =
    variant === "primary"
      ? "btn-primary"
      : variant === "danger"
        ? "btn-danger"
        : "btn-ghost";
  return (
    <button className={`${variantCls} ${sizeCls} ${className}`} {...rest}>
      {children}
    </button>
  );
}

export function PageHead({
  kicker,
  title,
  right,
}: {
  kicker: string;
  title: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <div className="mono text-[11px] uppercase tracking-[0.16em] text-faint">
          {kicker}
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">{title}</h1>
      </div>
      {right ? <div className="flex items-center gap-2">{right}</div> : null}
    </div>
  );
}

export function Panel({
  className = "",
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <section className={`panel p-5 ${className}`}>{children}</section>;
}

export function PanelTitle({
  children,
  hint,
}: {
  children: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h2 className="text-[12px] font-semibold uppercase tracking-[0.12em] text-faint">
        {children}
      </h2>
      {hint ? (
        <span className="mono text-[11px] text-faint">{hint}</span>
      ) : null}
    </div>
  );
}

export type ChipTone = "neutral" | "ok" | "warn" | "bad";

export function Chip({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: ChipTone;
}) {
  const tones: Record<ChipTone, string> = {
    neutral: "text-muted border-line",
    ok: "text-success border-success/40",
    warn: "text-warn border-warn/40",
    bad: "text-danger border-danger/40",
  };
  return <span className={`chip ${tones[tone]}`}>{children}</span>;
}

export function Dot({ tone }: { tone: "ok" | "bad" | "warn" | "idle" }) {
  const map = { ok: "bg-success", bad: "bg-danger", warn: "bg-warn", idle: "bg-faint" };
  return <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${map[tone]}`} />;
}

export function Progress({
  value,
  tone = "primary",
}: {
  value: number;
  tone?: "primary" | "success" | "danger";
}) {
  const bar = { primary: "bg-primary", success: "bg-success", danger: "bg-danger" }[tone];
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
      <div
        className={`h-full ${bar} rounded-full transition-[width] duration-300 ease-out`}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="block">
      {label ? (
        <div className="mb-1 flex items-baseline justify-between gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
            {label}
          </span>
          {hint ? <span className="mono text-[11px] text-faint">{hint}</span> : null}
        </div>
      ) : null}
      {children}
    </label>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`field ${props.className ?? ""}`} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea {...props} className={`field resize-y leading-relaxed ${props.className ?? ""}`} />
  );
}

export type NoticeTone = "info" | "ok" | "warn" | "bad";

export function Notice({
  children,
  tone = "info",
  onClose,
}: {
  children: ReactNode;
  tone?: NoticeTone;
  onClose?: () => void;
}) {
  const tones: Record<NoticeTone, string> = {
    info: "border-primary/30 text-body",
    ok: "border-success/40 text-success",
    warn: "border-warn/40 text-warn",
    bad: "border-danger/40 text-danger",
  };
  return (
    <div
      role="status"
      className={`flex items-start gap-2.5 rounded-[10px] border bg-surface px-3.5 py-2.5 text-sm ${tones[tone]}`}
    >
      <Dot tone={tone === "ok" ? "ok" : tone === "bad" ? "bad" : tone === "warn" ? "warn" : "idle"} />
      <div className="min-w-0 flex-1">{children}</div>
      {onClose ? (
        <button
          onClick={onClose}
          aria-label="Dismiss"
          className="opacity-60 transition-opacity hover:opacity-100"
        >
          <XIcon size={14} />
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  copy,
  action,
  icon,
}: {
  title: string;
  copy?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      {icon ? <div className="text-faint">{icon}</div> : null}
      <div>
        <div className="font-semibold text-ink">{title}</div>
        {copy ? <div className="mx-auto mt-1 max-w-sm text-sm text-faint">{copy}</div> : null}
      </div>
      {action}
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
}) {
  return (
    <div className="panel p-4">
      <div className="mono text-2xl font-semibold text-ink">{value}</div>
      <div className="mt-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
        {label}
      </div>
      {sub ? <div className="mt-1 text-xs leading-relaxed text-muted">{sub}</div> : null}
    </div>
  );
}