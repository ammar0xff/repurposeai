"""Sentence segmentation: punctuation + pauses + word timing. Stdlib only."""
import re

_SENT_END = re.compile(r"[.?!…:;]+$")


def to_sentences(words: list, max_gap: float = 0.9) -> list:
    sents, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["start"] - w["end"]) if nxt else 99.0
        if _SENT_END.search(w["w"]) or gap >= max_gap or nxt is None:
            sents.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                          "text": " ".join(x["w"] for x in cur)})
            cur = []
    return sents
