"""Caption engine: words -> timed groups -> ASS. Stdlib only."""

STYLES = {
    "clean": {"font": "DejaVu Sans", "size": 56, "bold": 0, "margin_v": 320},
    "bold": {"font": "DejaVu Sans", "size": 72, "bold": 1, "margin_v": 420},
    "minimal": {"font": "DejaVu Sans", "size": 48, "bold": 0, "margin_v": 220},
    "podcast": {"font": "DejaVu Sans", "size": 60, "bold": 1, "margin_v": 380},
    "karaoke": {"font": "DejaVu Sans", "size": 64, "bold": 1, "margin_v": 420},
}

HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},&H00FFFFFF,&H000019FF,&H80000000,&H80000000,{bold},0,0,0,100,100,0,0,1,3,1,5,60,60,{mv},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _fmt(t: float) -> str:
    t = max(0.0, t)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def segment(words: list, start: float, end: float, max_words: int = 4,
            max_chars: int = 42) -> list:
    """Group words into caption lines: sentence-aware, no overlap, sane timings."""
    wins, grp = [], []
    for w in words:
        if not (start - 0.3 <= w["start"] < end):
            continue
        grp.append(w)
        txt = " ".join(x["w"] for x in grp)
        if len(grp) >= max_words or len(txt) >= max_chars or txt.rstrip().endswith((".", "?", "!")):
            wins.append((max(grp[0]["start"], start), min(grp[-1]["end"], end), txt))
            grp = []
    if grp:
        wins.append((max(grp[0]["start"], start), min(grp[-1]["end"], end),
                     " ".join(x["w"] for x in grp)))
    clean = []
    for s, e, tx in wins:
        if e > s + 0.05 and tx.strip():
            clean.append((s, e, tx.strip()))
    return clean


def to_ass(words: list, start: float, end: float, style: str = "bold",
           max_words: int = 4, max_chars: int = 42) -> str:
    st = STYLES.get(style, STYLES["bold"])
    out = [HEAD.format(font=st["font"], size=st["size"], bold=st["bold"], mv=st["margin_v"])]
    for s, e, tx in segment(words, start, end, max_words, max_chars):
        safe = tx.replace("{", "(").replace("}", ")").upper()
        out.append(f"Dialogue: 0,{_fmt(s - start)},{_fmt(e - start)},Cap,,0,0,0,,"
                   f"{{\\fad(120,120)}}{safe}")
    if len(out) == 1:
        out.append(f"Dialogue: 0,{_fmt(0)},{_fmt(end - start)},Cap,,0,0,0,, ")
    return "\n".join(out) + "\n"
