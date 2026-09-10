"""Deterministic candidate generation + eligibility. Stdlib only.
Rule: LLM scores candidates; it never controls the timeline."""
import re

from .sentences import to_sentences

_SENT_END = re.compile(r"[.?!…:;]+$")
STOP_ASK = ("?", "!")


def _density(words, a, b):
    return sum(1 for w in words if a <= w["start"] < b) / max(b - a, 0.5)


def _edge(silence, t, tol=1.2):
    return any(abs(t - s) <= tol or abs(t - e) <= tol for s, e in silence)


def generate(words: list, duration: float, silence: list | None = None,
             cuts: list | None = None, min_s: float = 15, max_s: float = 60,
             step: float = 8) -> list:
    silence, cuts = silence or [], cuts or []
    sents = to_sentences(words)
    if not sents:
        return []
    starts = sorted({round(s["start"], 1) for s in sents})
    cands, seen = [], set()
    for L in {float(min_s), (float(min_s) + float(max_s)) / 2, float(max_s)}:
        t = 2.0
        while t + L <= duration + 1.0:
            st = min([s for s in starts if s >= t - 2.0] or [t])
            en = round(st + L, 1)
            seg = [w for w in words if st <= w["start"] < en]
            if len(seg) < 8:
                t += step
                continue
            key = (round(st), round(en))
            if key in seen:
                t += step
                continue
            seen.add(key)
            txt = " ".join(w["w"] for w in seg)
            cands.append({
                "start": round(st, 1), "end": en, "text": txt,
                "hook_text": " ".join(w["w"] for w in seg[:14]),
                "features": {
                    "density": round(_density(words, st, en), 2),
                    "words": len(seg),
                    "sil_edge": bool(_edge(silence, st) or _edge(silence, en)),
                    "scene_cuts": sum(1 for c in cuts if st < c < en),
                    "sent_complete": bool(_SENT_END.search(seg[-1]["w"])),
                    "has_question": any(q in txt for q in STOP_ASK),
                },
            })
            t += step
    return sorted(cands, key=lambda x: x["start"])


def eligible(cands: list, cfg: dict) -> list:
    """Eligibility BEFORE ranking. cfg: min/max_duration, min/max_words,
    require_sentence_complete, blacklisted_phrases, required_topics, excluded_topics."""
    lo, hi = float(cfg.get("min_duration", 15)), float(cfg.get("max_duration", 60))
    wlo, whi = int(cfg.get("min_words", 8)), int(cfg.get("max_words", 10**6))
    need_sent = bool(cfg.get("require_sentence_complete", False))
    banned = [b.lower() for b in cfg.get("blacklisted_phrases", [])]
    req = [r.lower() for r in cfg.get("required_topics", [])]
    exc = [e.lower() for e in cfg.get("excluded_topics", [])]
    out = []
    for c in cands:
        dur, txt = c["end"] - c["start"], c["text"].lower()
        if not (lo - 1 <= dur <= hi + 1):
            continue
        nw = c["features"]["words"]
        if not (wlo <= nw <= whi):
            continue
        if need_sent and not c["features"]["sent_complete"]:
            continue
        if any(b in txt for b in banned):
            continue
        if req and not any(r in txt for r in req):
            continue
        if any(e in txt for e in exc):
            continue
        out.append(c)
    return out
