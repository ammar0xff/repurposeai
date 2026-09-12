"""Montage stitching math: offsets, durations, transition maps."""

import pytest

from app.rendering.sequence import montage_filter, xfade_name


def test_xfade_name_aliases():
    assert xfade_name("crossfade") == "fade"
    assert xfade_name("dissolve") == "dissolve"
    assert xfade_name("zoom") == "zoomin"
    assert xfade_name("slide_left") == "slideleft"
    assert xfade_name("wipe") == "wipeleft"
    assert xfade_name(None) == "fade"
    assert xfade_name("cut") is None
    assert xfade_name("none") is None
    assert xfade_name("fadeblack") == "fadeblack"  # passthrough


def test_single_item_no_stitching():
    f, v, a, total = montage_filter([5.0], [None], [0.0])
    assert "xfade" not in f
    assert v == "[v0]" and a == "[a0]"
    assert total == 5.0


def test_offsets_accumulate_with_transition_overlap():
    # 3 x 10s clips, crossfades of 1 and 2s -> final duration 27s
    f, v, a, total = montage_filter(
        [10.0, 10.0, 10.0], [None, "crossfade", "zoom"], [0.0, 1.0, 2.0])
    assert total == pytest.approx(27.0)
    assert "xfade=transition=fade:duration=1.0000:offset=9.0000" in f
    assert "xfade=transition=zoomin:duration=2.0000:offset=17.0000" in f
    assert "acrossfade=d=1.0000" in f and "acrossfade=d=2.0000" in f
    assert f.endswith("[y2]") and "[x2]" in f and "[v0]" in f


def test_hard_cut_becomes_minimal_fade():
    f, *_ = montage_filter([10.0, 10.0], [None, "cut"], [0.0, 0.8])
    assert "transition=fade:duration=0.0500:offset=9.9500" in f


def test_transition_clamped_to_neighbour_duration():
    f, *_ = montage_filter([3.0, 10.0], [None, "crossfade"], [0.0, 8.0])
    assert "duration=3.0000" in f and "offset=0.0000" in f


def test_transition_duration_doubled_overlap_diffs():
    # different clip lengths still accumulate correctly
    f, _, _, total = montage_filter([20.0, 10.0, 15.0],
                                    [None, "crossfade", "slide_right"],
                                    [0.0, 1.0, 0.5])
    assert total == pytest.approx(43.5)


def test_default_transition_applied_when_missing():
    f, *_ = montage_filter([10.0, 10.0], [None], [0.0])
    assert "transition=fade:duration=0.8000" in f


def test_empty_raises():
    with pytest.raises(ValueError):
        montage_filter([], [None], [0.0])


def test_pairwise_step_totals_telescope_to_full():
    """Chunked stitching (1+2, then +3, ...) must yield the same running
    duration as one N-input filter graph, so intermediate re-encodes cannot
    drift the reported montage duration."""
    durations = [20.0, 10.0, 15.0, 12.0, 30.0]
    transitions = [None, "crossfade", "cut", "zoom", "crossfade"]
    tds = [0.0, 0.8, 0.8, 1.2, 0.5]
    _, _, _, full = montage_filter(durations, transitions, tds)

    acc = durations[0]
    for i in range(1, len(durations)):
        _, _, _, step_total = montage_filter(
            [acc, durations[i]], [None, transitions[i]], [0.0, tds[i]])
        acc = step_total
    assert abs(acc - full) < 1e-6


def test_master_audio_adds_loudnorm_and_limiter():
    f, v, a, total = montage_filter([5.0, 5.0], [None, "crossfade"],
                                    [0.0, 0.8], master_audio=True)
    assert "loudnorm=I=-14:TP=-1.5:LRA=11" in f
    assert ";[y1]alimiter=limit=0.891[amaster]" in f
    assert a == "[amaster]" and v == "[x1]"
    assert total == pytest.approx(9.2)


def test_master_audio_single_item():
    f, v, a, total = montage_filter([5.0], [None], [0.0], master_audio=True)
    assert "loudnorm=I=-14:TP=-1.5:LRA=11" in f
    assert "alimiter=limit=0.891" in f
    assert a == "[amaster]" and v == "[v0]"
    assert total == 5.0


def test_no_mastering_by_default():
    f, *_ = montage_filter([5.0, 5.0], [None, "crossfade"], [0.0, 0.8])
    assert "loudnorm" not in f and "alimiter" not in f