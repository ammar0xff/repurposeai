"""Timestamp resolver: approx range -> word/sentence boundaries + padding.
Deterministic. Never cuts mid-word. Clamps to source duration."""
from ..pipelines.sentences import to_sentences


def resolve(start: float, end: float, words: list, duration: float = 0.0,
            pad_before: float = 0.4, pad_after: float = 0.6,
            min_len: float = 5.0, max_len: float = 0.0) -> tuple[float, float]:
    if not words:
        return round(max(0.0, start), 1), round(max(0.0, end), 1)
    ws = sorted(words, key=lambda w: w["start"])
    st = min(ws, key=lambda w: abs(w["start"] - start))
    en = min(ws, key=lambda w: abs(w["end"] - end))
    s, e = st["start"] - pad_before, en["end"] + pad_after
    # snap end to sentence end when within 1.5s (avoid cutting payoff)
    for sn in to_sentences(words):
        if e < sn["end"] <= e + 1.5:
            e = sn["end"] + 0.2
            break
    s = max(0.0, s)
    if duration:
        e = min(float(duration), e)
    if e - s < min_len:
        e = s + min_len
    if max_len and e - s > max_len:
        e = s + max_len
    return round(s, 1), round(e, 1)
