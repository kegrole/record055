"""Fixed-frequency windowing: bucket assignment and bucket-range generation.

All math runs on naive wall-clock datetimes (UTC wall time when no timezone
is configured, local wall time otherwise), so calendar frequencies such as
1d and DST-aware 1h behave like a human reading a local clock.
"""

from datetime import datetime, timedelta

EPOCH = datetime(1970, 1, 1)

FREQS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}

# Each frequency's buckets cover whole parent periods, so the output span is
# a natural calendar range (an hour for sub-hourly freqs, a day for 1h/1d).
_PARENT = {"1m": "1h", "5m": "1h", "1h": "1d", "1d": "1d"}

CLOSED_MODES = ("left", "right", "both", "neither")
LABEL_MODES = ("left", "right")


def freq_delta(freq):
    try:
        return FREQS[freq]
    except KeyError:
        raise ValueError(
            "unsupported frequency %r (choose from %s)"
            % (freq, ", ".join(sorted(FREQS)))
        )


def _micros(dt):
    d = dt - EPOCH
    return (d.days * 86400 + d.seconds) * 1_000_000 + d.microseconds


def _from_micros(us):
    return EPOCH + timedelta(microseconds=us)


def floor_dt(dt, delta):
    """Largest delta-aligned (since epoch) datetime not after dt."""
    step = _micros(EPOCH + delta)
    us = _micros(dt)
    return _from_micros(us - us % step)


def bucket_starts_for(dt, delta, closed):
    """Bucket-start datetimes a point at dt belongs to, given closed mode.

    left:    [start, end)   right: (start, end]
    both:    [start, end]   neither: (start, end)
    """
    step = _micros(EPOCH + delta)
    us = _micros(dt)
    on_boundary = us % step == 0
    if closed == "left":
        return [_from_micros(us - us % step)]
    if closed == "right":
        shifted = us - 1
        return [_from_micros(shifted - shifted % step)]
    if closed == "both":
        first = us - us % step
        starts = [first]
        if on_boundary:
            starts.append(first - step)
        return [_from_micros(s) for s in starts]
    if closed == "neither":
        if on_boundary:
            return []
        return [_from_micros(us - us % step)]
    raise ValueError(
        "invalid closed mode %r (choose from %s)" % (closed, ", ".join(CLOSED_MODES))
    )


def bucket_range(min_wall, max_wall, freq, extra_start=None):
    """All bucket-start datetimes covering the data span.

    The range starts at the freq-aligned floor of the earliest point (or an
    earlier assigned bucket, e.g. closed=right on a boundary point) and ends
    at the end of the parent period containing the latest point.
    """
    delta = freq_delta(freq)
    parent = freq_delta(_PARENT[freq])
    start = floor_dt(min_wall, delta)
    if extra_start is not None and extra_start < start:
        start = extra_start
    end = floor_dt(max_wall, parent) + parent
    buckets = []
    t = start
    while t < end:
        buckets.append(t)
        t += delta
    return buckets
