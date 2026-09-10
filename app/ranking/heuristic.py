"""Deterministic heuristic scoring. Same schema as the LLM path.
Visible labeling: results carry source='heuristic' (No Fake AI rule)."""
from ..providers.llm import overall


def score_candidates(cands: list, words: list, duration: float, n: int = 5) -> list:
    from .resolve import resolve
    scored = []
    for i, c in enumerate(cands):
        f = c.get("features", {})
        axes = {
            "hook": min(10, 4 + f.get("density", 1.5) * 2),
            "standalone": 7 if f.get("sent_complete") else 4,
            "payoff": 7 if f.get("sent_complete") else 4,
            "clarity": min(10, 3 + len(c.get("text", "")) / 60),
            "emotion": 6 if f.get("has_question") else 5,
            "retention": 5 + (2 if f.get("sil_edge") else 0) - min(3, f.get("scene_cuts", 0)),
        }
        axes = {k: round(max(0, min(10, v)), 1) for k, v in axes.items()}
        rs, re = resolve(c["start"], c["end"], words, duration)
        scored.append({"candidate": i, "start": rs, "end": re,
                       "score": round(overall(axes) * 10, 1), "axes": axes,
                       "title": c.get("hook_text", "")[:60],
                       "caption": c.get("text", "")[:150],
                       "hook_text": c.get("hook_text", ""),
                       "reason": "heuristic", "source": "heuristic"})
    scored.sort(key=lambda m: -m["score"])
    picked = []
    for m in scored:
        if all(m["end"] <= p["start"] or m["start"] >= p["end"] for p in picked):
            picked.append(m)
        if len(picked) == n:
            break
    return sorted(picked, key=lambda m: m["start"])
