"""
tests/test_timeline_validator.py

Tests for timeline overflow/collision validation logic in the DubStudio backend.
Covers fit_segments_to_audio_duration and sanitize_segments_timeline logic.

Run with: pytest tests/test_timeline_validator.py -v
"""
import pytest

# ---------------------------------------------------------------------------
# Inline validation functions mirroring stt_engine.py / main.py logic
# ---------------------------------------------------------------------------

def fit_segments_to_audio_duration(segments, max_duration):
    """Clamp end times; only last segment gets tail-rebalancing."""
    if not segments or max_duration <= 0:
        return segments
    result = []
    for i, seg in enumerate(segments):
        seg = dict(seg)
        start = max(0.0, float(seg.get("start", 0)))
        end = float(seg.get("end", 0))
        if end <= start:
            end = start + 1.0
        is_last = (i == len(segments) - 1)
        if is_last:
            if end > max_duration:
                orig_dur = end - start
                end = max_duration
                start = max(0.0, end - max(1.0, orig_dur))
        else:
            if end > max_duration:
                end = max_duration
            if start >= max_duration:
                start = max(0.0, max_duration - 0.5)
        seg["start"] = round(start, 2)
        seg["end"]   = round(end,   2)
        result.append(seg)
    return result


def sanitize_segments_timeline(segments, max_duration, min_gap=0.05):
    """Resolve collisions and clamp end times."""
    if not segments:
        return segments
    sorted_segs = sorted(segments, key=lambda s: float(s.get("start", 0)))
    out = []
    prev_end = 0.0
    for seg in sorted_segs:
        seg = dict(seg)
        start = max(0.0, float(seg.get("start", 0)))
        end   = float(seg.get("end", 0))
        if end <= start:
            end = start + 1.0
        if out and start < prev_end:
            prev = out[-1]
            trimmed = max(float(prev["start"]) + 0.25, start - min_gap)
            prev["end"] = round(trimmed, 2)
            prev_end = prev["end"]
            start = round(prev_end + min_gap, 2)
        if max_duration > 0 and end > max_duration:
            end = max_duration
        seg["start"] = round(start, 2)
        seg["end"]   = round(end,   2)
        prev_end = end
        out.append(seg)
    return out


def validate_before_export(segments, max_duration):
    """Returns (can_export, blockers)."""
    blockers = []
    for seg in segments:
        start  = float(seg.get("start", 0))
        end    = float(seg.get("end",   0))
        seg_id = seg.get("id", "?")
        if start < 0:
            blockers.append(f"#{seg_id}: starts before 00:00 ({start:.2f}s)")
        if end <= start:
            blockers.append(f"#{seg_id}: negative/zero duration ({start:.2f}->{end:.2f})")
        if max_duration > 0 and end > max_duration + 0.005:
            overflow = round(end - max_duration, 2)
            blockers.append(f"#{seg_id}: overflow +{overflow:.2f}s")
    return len(blockers) == 0, blockers


VIDEO_DURATION = 30.0
def seg(id, start, end): return {"id": id, "start": start, "end": end, "text": "Hello"}


# ===========================================================================
# Test cases
# ===========================================================================

def test_subtitle_completely_inside_video():
    """Subtitles that end well before video duration - no clamping needed."""
    segs = [seg(1, 0.0, 5.0), seg(2, 5.5, 10.0)]
    result = fit_segments_to_audio_duration(segs, VIDEO_DURATION)
    for s in result:
        assert s["end"] <= VIDEO_DURATION


def test_subtitle_ending_exactly_at_video_duration():
    """Subtitle ending at exactly 30.00s must NOT be modified."""
    segs = [seg(1, 28.0, 30.0)]
    result = fit_segments_to_audio_duration(segs, VIDEO_DURATION)
    assert result[0]["end"] == 30.0


def test_subtitle_exceeding_video_duration():
    """The core case: subtitle #9 at 28.36->30.61 must be clamped to 30.00."""
    segs = [seg(9, 28.36, 30.61)]
    result = fit_segments_to_audio_duration(segs, VIDEO_DURATION)
    assert result[0]["end"] <= VIDEO_DURATION
    assert result[0]["end"] == VIDEO_DURATION


def test_middle_segment_not_rebalanced():
    """Middle segments that overflow must be clamped, NOT moved to video tail."""
    segs = [seg(1, 0.0, 5.0), seg(2, 5.1, 30.61), seg(3, 28.0, 30.0)]
    result = fit_segments_to_audio_duration(segs, VIDEO_DURATION)
    # Segment 2 must still be near its original position
    assert result[1]["end"] <= VIDEO_DURATION
    assert result[1]["start"] < 10.0, f"Middle seg rebalanced: start={result[1]['start']}"


def test_subtitle_starting_before_zero():
    """Negative start time must be clamped to 0."""
    segs = [seg(1, -2.0, 5.0)]
    result = fit_segments_to_audio_duration(segs, VIDEO_DURATION)
    assert result[0]["start"] >= 0.0


def test_negative_duration_segment():
    """Segment where end < start must have its duration corrected."""
    segs = [seg(1, 10.0, 5.0)]
    result = fit_segments_to_audio_duration(segs, VIDEO_DURATION)
    assert result[0]["end"] > result[0]["start"]


def test_subtitle_collision():
    """Segment A (20-25) overlaps Segment B (24.5-28) by 0.5s - must resolve."""
    segs = [seg(1, 20.0, 25.0), seg(2, 24.5, 28.0)]
    result = sanitize_segments_timeline(segs, VIDEO_DURATION)
    assert result[0]["end"] < result[1]["start"] + 0.001, (
        f"Collision not resolved: {result[0]['end']} vs {result[1]['start']}"
    )


def test_multiple_subtitle_overflows():
    """All overflowing segments must be clamped to video duration."""
    segs = [seg(1, 0.0, 31.0), seg(2, 5.0, 35.0), seg(3, 28.0, 30.8)]
    result = fit_segments_to_audio_duration(segs, VIDEO_DURATION)
    for s in result:
        assert s["end"] <= VIDEO_DURATION, f"Segment {s['id']} still overflows: {s['end']}"


def test_auto_fix_overflow_allows_export():
    """After clamping overflow, validateBeforeExport must pass."""
    segs = [seg(9, 28.36, 30.61)]
    fixed = fit_segments_to_audio_duration(segs, VIDEO_DURATION)
    can_export, blockers = validate_before_export(fixed, VIDEO_DURATION)
    assert can_export, f"Export blocked after fix. Blockers: {blockers}"


def test_export_blocked_when_overflow_exists():
    """validateBeforeExport must BLOCK unfixed overflow."""
    segs = [seg(9, 28.36, 30.61)]
    can_export, blockers = validate_before_export(segs, VIDEO_DURATION)
    assert not can_export
    assert blockers


def test_export_allowed_when_all_clean():
    """All subtitles within bounds -> export gate passes."""
    segs = [seg(1, 0.0, 5.0), seg(2, 5.5, 12.0), seg(3, 13.0, 20.0), seg(4, 21.0, 29.5)]
    can_export, blockers = validate_before_export(segs, VIDEO_DURATION)
    assert can_export, f"Clean subs blocked export: {blockers}"


def test_export_blocked_on_negative_start():
    """Subtitle with start < 0 must block export."""
    segs = [seg(1, -1.0, 5.0)]
    can_export, _ = validate_before_export(segs, VIDEO_DURATION)
    assert not can_export


def test_export_blocked_on_zero_duration():
    """Subtitle with end == start (zero duration) must block export."""
    segs = [seg(1, 5.0, 5.0)]
    can_export, _ = validate_before_export(segs, VIDEO_DURATION)
    assert not can_export
