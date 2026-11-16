"""Report shaping: JSON records, file output, and summary lines."""

import json
import os


def to_json_records(records):
    """Convert resample records to JSON-serializable dicts."""
    return [
        {
            "bucket_start": r["bucket_start"].isoformat(),
            "value": r["value"],
            "filled": r["filled"],
        }
        for r in records
    ]


def summarize(raw_count, records):
    """Build the summary dict for a resample run."""
    return {
        "raw_points": raw_count,
        "buckets": len(records),
        "empty_buckets": sum(1 for r in records if r["value"] is None),
        "filled_points": sum(1 for r in records if r["filled"]),
    }


def summary_line(summary):
    return (
        "summary: raw_points={raw_points} buckets={buckets} "
        "empty_buckets={empty_buckets} filled_points={filled_points}"
    ).format(**summary)


def write_report(records, summary, path):
    """Write {"summary": ..., "buckets": [...]} as JSON to path."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    payload = {"summary": summary, "buckets": to_json_records(records)}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
