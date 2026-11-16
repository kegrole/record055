"""Acceptance tests for the resample package.

Covers the nine judging criteria: bucket span, first-bucket label, null
empty buckets, config-driven interpolation, no extrapolation, closed
semantics on boundary points, DST-aware local bucketing, and the report
schema.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resample.report import to_json_records
from resample.series import Point, resample
from resample.tz import parse_timestamp

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTC = timezone.utc


def build_dataset1():
    """One hour of 5-minute data, 12 points, timestamps carry +00:00."""
    base = datetime(2026, 3, 10, 0, 0, tzinfo=UTC)
    return [
        Point(ts=base + timedelta(minutes=5 * i), value=float((i + 1) * 10))
        for i in range(12)
    ]


def build_dataset2():
    """Dataset 1 with the 00:30 sample removed: one 10-minute gap."""
    return [p for p in build_dataset1() if p.ts.minute != 30]


def build_dataset3():
    """Europe/Berlin DST fallback day 2026-10-25 (25 real hours).

    Half-hourly points covering local 00:00 through 23:59; local 02:00-02:59
    occurs twice (CEST then CET), so the day has 25 real hours.
    """
    start = datetime(2026, 10, 24, 22, 0, tzinfo=UTC)  # local 2026-10-25 00:00
    return [
        Point(ts=start + timedelta(minutes=30 * i), value=1.0)
        for i in range(50)
    ]


def dataset1_csv_text():
    lines = ["timestamp,value"]
    for p in build_dataset1():
        lines.append("%s,%s" % (p.ts.isoformat(), p.value))
    return "\n".join(lines) + "\n"


def values_between(records, start_iso, end_iso):
    start = parse_timestamp(start_iso)
    end = parse_timestamp(end_iso)
    return [
        r for r in records
        if start <= r["bucket_start"].astimezone(UTC) <= end
    ]


class TestFixtures(unittest.TestCase):
    """Criterion 1: the three datasets exist and obey the stated rules."""

    def test_dataset1_shape(self):
        ds = build_dataset1()
        self.assertEqual(len(ds), 12)
        self.assertEqual(ds[0].ts.isoformat(), "2026-03-10T00:00:00+00:00")
        deltas = {ds[i + 1].ts - ds[i].ts for i in range(11)}
        self.assertEqual(deltas, {timedelta(minutes=5)})

    def test_dataset2_has_one_ten_minute_gap(self):
        ds = build_dataset2()
        self.assertEqual(len(ds), 11)
        gaps = [ds[i + 1].ts - ds[i].ts for i in range(len(ds) - 1)]
        self.assertEqual(gaps.count(timedelta(minutes=10)), 1)
        self.assertEqual(gaps.count(timedelta(minutes=5)), 9)

    def test_dataset3_dst_day_has_25_real_hours(self):
        ds = build_dataset3()
        span = ds[-1].ts - ds[0].ts
        self.assertEqual(span, timedelta(hours=24, minutes=30))
        # local wall clock sees 24 hourly labels, 02:00 twice
        from resample.tz import get_timezone
        berlin = get_timezone("Europe/Berlin")
        hours = [p.ts.astimezone(berlin).hour for p in ds]
        self.assertEqual(hours.count(2), 4)  # 2 half-hour points x 2 passes

    def test_demo_csv_matches_dataset1(self):
        path = os.path.join(REPO_ROOT, "demo", "series.csv")
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), dataset1_csv_text())


class TestBucketSpan(unittest.TestCase):
    """Criteria 2, 3 and 6: span, first label, no extrapolation."""

    def test_1m_resample_covers_60_buckets_with_12_non_empty(self):
        records = resample(build_dataset1(), "1m", agg="count")
        self.assertEqual(len(records), 60)
        non_empty = [r for r in records if r["value"] is not None]
        self.assertEqual(len(non_empty), 12)
        self.assertEqual(sum(r["value"] for r in non_empty), 12)

    def test_first_bucket_start_is_midnight_utc(self):
        records = resample(build_dataset1(), "1m", agg="count")
        self.assertEqual(
            records[0]["bucket_start"].isoformat(),
            "2026-03-10T00:00:00+00:00",
        )

    def test_offsets_normalize_to_utc(self):
        self.assertEqual(
            parse_timestamp("2026-03-10T01:00:00+01:00"),
            parse_timestamp("2026-03-10T00:00:00+00:00"),
        )

    def test_no_extrapolation_after_series_end(self):
        records = resample(build_dataset1(), "1m", agg="mean", max_gap=5)
        self.assertIsNone(records[-1]["value"])
        self.assertFalse(records[-1]["filled"])
        # every bucket after the last data point stays null
        last_data = parse_timestamp("2026-03-10T00:55:00+00:00")
        trailing = [r for r in records if r["bucket_start"] > last_data]
        self.assertTrue(trailing)
        self.assertTrue(all(r["value"] is None for r in trailing))


class TestGapFilling(unittest.TestCase):
    """Criteria 4 and 5: null empty buckets, config-driven filling."""

    def test_empty_bucket_is_null_not_zero(self):
        records = resample(build_dataset2(), "5m", agg="mean", max_gap=0)
        gap = values_between(
            records, "2026-03-10T00:30:00+00:00", "2026-03-10T00:30:00+00:00"
        )
        self.assertEqual(len(gap), 1)
        self.assertIsNone(gap[0]["value"])
        self.assertNotEqual(gap[0]["value"], 0)

    def test_linear_fill_inserts_exactly_one_point(self):
        records = resample(build_dataset2(), "5m", agg="mean", max_gap=3)
        segment = values_between(
            records, "2026-03-10T00:25:00+00:00", "2026-03-10T00:35:00+00:00"
        )
        non_null = [r for r in segment if r["value"] is not None]
        self.assertEqual(len(non_null), 3)
        inserted = [r for r in segment if r["filled"]]
        self.assertEqual(len(inserted), 1)
        self.assertEqual(
            inserted[0]["bucket_start"].isoformat(),
            "2026-03-10T00:30:00+00:00",
        )
        self.assertAlmostEqual(inserted[0]["value"], 70.0)

    def test_max_gap_zero_disables_filling(self):
        records = resample(build_dataset2(), "5m", agg="mean", max_gap=0)
        segment = values_between(
            records, "2026-03-10T00:25:00+00:00", "2026-03-10T00:35:00+00:00"
        )
        non_null = [r for r in segment if r["value"] is not None]
        self.assertEqual(len(non_null), 2)
        self.assertFalse(any(r["filled"] for r in records))


class TestClosedSemantics(unittest.TestCase):
    """Criterion 7: boundary points land in different buckets."""

    def setUp(self):
        self.point = [Point(ts=parse_timestamp("2026-03-10T00:05:00+00:00"),
                            value=42.0)]

    def test_closed_left_puts_boundary_point_in_own_bucket(self):
        records = resample(self.point, "5m", closed="left", agg="last")
        hit = [r for r in records if r["value"] == 42.0]
        self.assertEqual(len(hit), 1)
        self.assertEqual(
            hit[0]["bucket_start"].isoformat(), "2026-03-10T00:05:00+00:00"
        )

    def test_closed_right_puts_boundary_point_in_previous_bucket(self):
        records = resample(self.point, "5m", closed="right", agg="last")
        hit = [r for r in records if r["value"] == 42.0]
        self.assertEqual(len(hit), 1)
        self.assertEqual(
            hit[0]["bucket_start"].isoformat(), "2026-03-10T00:00:00+00:00"
        )

    def test_closed_modes_disagree_on_boundary_point(self):
        left = resample(self.point, "5m", closed="left", agg="last")
        right = resample(self.point, "5m", closed="right", agg="last")
        left_bucket = next(r for r in left if r["value"] == 42.0)
        right_bucket = next(r for r in right if r["value"] == 42.0)
        self.assertNotEqual(left_bucket["bucket_start"],
                            right_bucket["bucket_start"])


class TestDstBucketing(unittest.TestCase):
    """Criterion 8: DST day cut on local wall-clock labels."""

    def test_1h_gives_24_buckets_with_single_0200_bucket(self):
        records = resample(build_dataset3(), "1h", agg="count",
                           timezone_name="Europe/Berlin")
        self.assertEqual(len(records), 24)
        local_labels = [
            r["bucket_start"].replace(tzinfo=None) for r in records
        ]
        self.assertEqual(len(set(local_labels)), 24)
        two_am = [r for r in records
                  if r["bucket_start"].replace(tzinfo=None)
                  == datetime(2026, 10, 25, 2, 0)]
        self.assertEqual(len(two_am), 1)
        self.assertEqual(two_am[0]["value"], 4)  # both 02:00 passes, 30-min data
        self.assertEqual(
            two_am[0]["bucket_start"].isoformat(),
            "2026-10-25T02:00:00+02:00",
        )
        total = sum(r["value"] for r in records if r["value"] is not None)
        self.assertEqual(total, 50)

    def test_1d_gives_exactly_one_bucket(self):
        records = resample(build_dataset3(), "1d", agg="count",
                           timezone_name="Europe/Berlin")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["value"], 50)
        self.assertEqual(
            records[0]["bucket_start"].replace(tzinfo=None),
            datetime(2026, 10, 25, 0, 0),
        )


class TestReportSchema(unittest.TestCase):
    """Criterion 9: every record carries bucket_start, value, filled."""

    def test_report_records_have_exactly_three_fields(self):
        records = resample(build_dataset1(), "1m", agg="mean", max_gap=3)
        payload = to_json_records(records)
        self.assertEqual(len(payload), 60)
        for entry in payload:
            self.assertEqual(
                set(entry.keys()), {"bucket_start", "value", "filled"}
            )
            parsed = datetime.fromisoformat(entry["bucket_start"])
            self.assertIsNotNone(parsed.tzinfo)
            self.assertIsInstance(entry["filled"], bool)


if __name__ == "__main__":
    unittest.main()
