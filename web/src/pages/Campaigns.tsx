import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Campaign, get, post } from "../api";
import {
  Button,
  Chip,
  EmptyState,
  Field,
  Input,
  Notice,
  PageHead,
  Panel,
} from "../components/ui";
import { CampaignIcon } from "../icons";
import type { NoticeTone } from "../components/ui";

export default function Campaigns() {
  const [list, setList] = useState<Campaign[]>([]);
  const [name, setName] = useState("");
  const [note, setNote] = useState<{ tone: NoticeTone; msg: string } | null>(null);

  const load = () =>
    void get<{ items: Campaign[] }>("/api/campaigns")
      .then((r) => setList(r.items))
      .catch(() => {});

  useEffect(load, []);

  const create = async () => {
    if (!name.trim()) return;
    try {
      await post("/api/campaigns", { name, rules: {}, verified: false });
      setName("");
      load();
    } catch (e) {
      setNote({
        tone: "bad",
        msg: e instanceof Error ? e.message : "Could not create campaign.",
      });
    }
  };

  return (
    <div>
      <PageHead
        kicker="Policy"
        title="Campaigns"
        right={
          list.length ? (
            <span className="mono text-xs text-faint">{list.length} tracked</span>
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

      <Panel className="mb-5">
        <Field label="New campaign">
          <div className="flex gap-2">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void create()}
              placeholder="e.g. Q3 launch, payout 0.35/1k"
            />
            <Button variant="primary" onClick={() => void create()}>
              Create
            </Button>
          </div>
        </Field>
      </Panel>

      {list.length ? (
        <div className="space-y-3">
          {list.map((c) => (
            <div key={c.id} className="panel flex items-center gap-3 p-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] border border-line text-faint">
                <CampaignIcon size={18} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate font-semibold text-ink">{c.name}</div>
                <div className="mono mt-0.5 text-[11px] text-faint">
                  v{c.version}
                  {c.p0_missing?.length ? ` · ${c.p0_missing.length} p0 fields missing` : ""}
                </div>
              </div>
              <Chip tone={c.ready ? "ok" : "bad"}>
                {c.ready ? "ready" : `blocked ${c.blockers?.length ?? 0}`}
              </Chip>
              <Link to={`/campaign/${c.id}`}>
                <Button variant="ghost" size="sm">
                  Open
                </Button>
              </Link>
            </div>
          ))}
        </div>
      ) : (
        <Panel>
          <EmptyState
            icon={<CampaignIcon size={26} />}
            title="No campaigns yet"
            copy="A campaign is a paid-content brief: rate per 1k, budget, duration cap and credit rules. Generate respects it; posting stays manual."
            action={
              <span className="text-xs text-faint">Create one to gate production clips.</span>
            }
          />
        </Panel>
      )}
    </div>
  );
}