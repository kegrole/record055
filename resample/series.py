"""Core resampling pipeline: load points, bucket them, aggregate, fill."""

import csv
from dataclasses import dataclass
from datetime import datetime

from . import tz as tzmod
from .agg import aggregate
from .interpolate import linear_fill
from .windows import bucket_range, bucket_starts_for, freq_delta


@dataclass
class Point:
    ts: datetime  # aware, normalized to UTC
    value: float


def load_csv(path):
    """Load a CSV with columns timestamp,value into UTC-normalized points."""
    points = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            points.append(
                Point(ts=tzmod.parse_timestamp(row["timestamp"]),
                      value=float(row["value"]))
            )
    return points


def resample(points, freq, closed="left", label="left", agg="mean",
             timezone_name=None, max_gap=0):
    """Resample points into fixed-frequency buckets.

    Returns a list of records: {"bucket_start": aware datetime,
    "value": float | None, "filled": bool}.
    """
    if not points:
        return []
    delta = freq_delta(freq)
    tzinfo = tzmod.get_timezone(timezone_name)

    ordered = sorted(points, key=lambda p: p.ts)
    wall = [(tzmod.to_wall(p.ts, tzinfo), p.value) for p in ordered]

    assigned = []
    for w, value in wall:
        starts = bucket_starts_for(w, delta, closed)
        assigned.append((starts, value))
    all_starts = [s for starts, _ in assigned for s in starts]
    extra_start = min(all_starts) if all_starts else None

    starts = bucket_range(wall[0][0], wall[-1][0], freq,
                          extra_start=extra_start)
    buckets = {s: [] for s in starts}
    for point_starts, value in assigned:
        for s in point_starts:
            if s in buckets:
                buckets[s].append(value)

    records = []
    for s in starts:
        out_start = s if label == "left" else s + delta
        records.append({
            "bucket_start": tzmod.localize(out_start, tzinfo),
            "value": aggregate(agg, buckets[s]),
            "filled": False,
        })

    if max_gap > 0:
        linear_fill(records, max_gap)
    return records
