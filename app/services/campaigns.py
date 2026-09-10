"""Campaign policy: versioned rules are the single source of truth.
P0 fields gate production runs; blockers() adds unverified conflicts and
assumptions. Ported from the whopclip merge (battle-tested wording kept)."""
from ..core.ids import new_id

P0_FIELDS = ["rate_per_1k", "budget", "sources", "duration.min", "duration.max",
             "hashtags", "credit.text", "cap"]


def _get(d: dict, dotted: str):
    cur = d
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _filled(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip()) and "FILL" not in v
    if isinstance(v, (list, tuple)):
        return len(v) > 0 and all("FILL" not in str(x) for x in v)
    if isinstance(v, (int, float)):
        return True
    return isinstance(v, dict)


def p0_missing(rules: dict) -> list:
    return [f for f in P0_FIELDS if not _filled(_get(rules, f))]


def blockers(rules: dict, verified: bool = False) -> list:
    """Everything stopping a PRODUCTION run. [] = cleared for submission.
    Dry-runs bypass this; never submit on a bypassed run."""
    rules = rules or {}
    b = list(p0_missing(rules))
    if not verified:
        extra = ([f"conflict:{c}" for c in rules.get("conflicts", [])]
                 + [f"assumed:{a}" for a in rules.get("assumptions", [])])
        b += extra or ["unverified: no conflicts/assumptions recorded"]
    return b


def bounds(rules: dict) -> tuple[float, float]:
    d = rules.get("duration", {}) or {}
    return float(d.get("min", 15)), float(d.get("max", 60))


def to_project_config(rules: dict) -> dict:
    """Map campaign rules onto pipeline config keys."""
    lo, hi = bounds(rules)
    credit = rules.get("credit", {}) or {}
    return {"min_duration": lo, "max_duration": hi,
            "hashtags": list(rules.get("hashtags", [])),
            "credit": credit.get("text", "") if credit.get("required") else "",
            "require_sentence_complete": False}


def create_from_dict(db, user_id: str, name: str, rules: dict,
                     verified: bool = False):
    from ..models.entities import Campaign
    camp = Campaign(id=new_id(), user_id=user_id, name=name[:128],
                    rules=dict(rules), verified=verified)
    db.add(camp)
    db.commit()
    return camp
