"""Ranking service: structured LLM scoring (+Pydantic when available),
retry-once on invalid JSON, heuristic fallback. Never crashes on bad LLM output."""
from ..providers.llm import overall


def _validate_records(recs: list, want_ids: set) -> list:
    """Pydantic if importable, else manual validation. Same contract."""
    try:
        from pydantic import BaseModel, Field

        class Axes(BaseModel):
            hook: float = Field(ge=0, le=10)
            standalone: float = Field(ge=0, le=10)
            payoff: float = Field(ge=0, le=10)
            clarity: float = Field(ge=0, le=10)
            emotion: float = Field(ge=0, le=10)
            retention: float = Field(ge=0, le=10)

        class Rec(BaseModel):
            id: int
            axes: Axes
            title: str = ""
            caption: str = ""
            reason: str = ""

        out = []
        for r in recs:
            if not isinstance(r, dict) or r.get("id") not in want_ids:
                continue
            rec = Rec.model_validate(r)
            out.append({"id": rec.id, "axes": rec.axes.model_dump(),
                        "overall": overall(rec.axes.model_dump()),
                        "title": rec.title, "caption": rec.caption,
                        "reason": rec.reason})
        return out
    except ImportError:
        out = []
        for r in recs:
            if not isinstance(r, dict) or r.get("id") not in want_ids:
                continue
            try:
                axes = {k: max(0.0, min(10.0, float(r.get(k, 5)))) for k in
                        ("hook", "standalone", "payoff", "clarity", "emotion", "retention")}
            except (TypeError, ValueError):
                continue
            out.append({"id": r["id"], "axes": axes, "overall": overall(axes),
                        "title": str(r.get("title", "")),
                        "caption": str(r.get("caption", "")),
                        "reason": str(r.get("reason", ""))})
        return out


def rank(cands: list, words: list, duration: float, n: int,
         provider, model: str = "") -> tuple[list, str]:
    """Returns (moments, source_label). source is 'llm:<name>' or 'heuristic'."""
    from ..ranking.resolve import resolve
    from .heuristic import score_candidates
    recs, via = provider.score_safe(
        [{"id": i, "start": c["start"], "end": c["end"],
          "hook_text": c.get("hook_text", ""), "text": c.get("text", "")}
         for i, c in enumerate(cands)], model)
    if recs:
        valid = _validate_records(recs, set(range(len(cands))))
        if valid:
            moms = []
            for r in sorted(valid, key=lambda x: -x["overall"]):
                c = cands[r["id"]]
                rs, re = resolve(c["start"], c["end"], words, duration)
                moms.append({"candidate": r["id"], "start": rs, "end": re,
                             "score": round(r["overall"] * 10, 1), "axes": r["axes"],
                             "title": r["title"] or c.get("hook_text", "")[:60],
                             "caption": r["caption"] or c.get("text", "")[:150],
                             "hook_text": c.get("hook_text", ""),
                             "reason": r["reason"], "source": via,
                             "prompt_version": r.get("prompt_version", "ranking/v1"),
                             "model": r.get("model", model)})
                if len(moms) == n:
                    break
            moms.sort(key=lambda m: -m["score"])
            picked = []
            for m in moms:
                if all(m["end"] <= q["start"] or m["start"] >= q["end"] for q in picked):
                    picked.append(m)
                if len(picked) == n:
                    break
            return sorted(picked, key=lambda m: m["start"]), via
    moms = score_candidates(cands, words, duration, n)
    return moms, "heuristic"
