import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { errMsg } from "../lib/jobstream";
import { Button, Field, Input, Notice } from "../components/ui";
import { PlayIcon } from "../icons";

export default function Login() {
  const { login, setup } = useAuth();
  const [mode, setMode] = useState<"in" | "create">("in");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "in") await login(username.trim(), password);
      else await setup(username.trim(), password);
    } catch (err) {
      setError(errMsg(err));
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-16">
      <div className="mb-8 flex flex-col items-center gap-3 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/15 text-primary">
          <PlayIcon size={26} />
        </span>
        <div>
          <div className="text-lg font-bold tracking-tight text-ink">
            Repurpose<span className="text-primary">AI</span>
          </div>
          <div className="mt-1 text-sm text-faint">Long video in. Shorts out.</div>
        </div>
      </div>

      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl border border-line bg-surface p-6 shadow-ambient-sm"
      >
        <div className="mb-5 grid grid-cols-2 gap-1 rounded-[10px] border border-line bg-surface-2 p-1">
          {(["in", "create"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => {
                setMode(m);
                setError("");
              }}
              className={`rounded-lg px-3 py-1.5 text-[13px] font-semibold transition-colors duration-150 ${
                mode === m ? "bg-surface-3 text-ink" : "text-faint hover:text-muted"
              }`}
            >
              {m === "in" ? "Sign in" : "First run"}
            </button>
          ))}
        </div>

        <div className="space-y-3.5">
          <Field label="Username">
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              minLength={2}
              required
              placeholder="you"
            />
          </Field>
          <Field
            label="Password"
            hint={mode === "create" ? "10+ chars" : undefined}
          >
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "in" ? "current-password" : "new-password"}
              minLength={10}
              required
              placeholder="••••••••••"
            />
          </Field>
        </div>

        {error ? (
          <div className="mt-4">
            <Notice tone="bad">{error}</Notice>
          </div>
        ) : null}

        <Button
          type="submit"
          variant="primary"
          className="mt-5 w-full"
          disabled={busy}
        >
          {busy
            ? mode === "in"
              ? "Signing in..."
              : "Creating your password..."
            : mode === "in"
              ? "Sign in"
              : "Create password and sign in"}
        </Button>

        <p className="mt-4 text-center text-[11px] leading-relaxed text-faint">
          This box is password-protected. Tokens are stored only in your browser.
        </p>
      </form>
    </div>
  );
}