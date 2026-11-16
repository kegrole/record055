"""Command-line interface: resample a CSV series into a JSON report."""

import argparse
import sys

from .agg import AGGREGATIONS
from .report import summarize, summary_line, write_report
from .series import load_csv, resample
from .windows import CLOSED_MODES, FREQS, LABEL_MODES


def build_parser():
    parser = argparse.ArgumentParser(
        prog="resample",
        description="Resample an irregular time series into fixed-frequency "
        "buckets and write a JSON report.",
    )
    parser.add_argument("--input", required=True,
                        help="CSV file with columns timestamp,value")
    parser.add_argument("--freq", required=True, choices=sorted(FREQS),
                        help="target bucket frequency")
    parser.add_argument("--out", help="write the JSON report to this path")
    parser.add_argument("--agg", default="mean", choices=sorted(AGGREGATIONS),
                        help="aggregation applied inside each bucket "
                        "(default: mean)")
    parser.add_argument("--closed", default="left", choices=CLOSED_MODES,
                        help="which window edge is closed (default: left)")
    parser.add_argument("--label", default="left", choices=LABEL_MODES,
                        help="which window edge labels the bucket "
                        "(default: left)")
    parser.add_argument("--tz", default=None, metavar="TZ",
                        help="IANA timezone (e.g. Europe/Berlin); buckets "
                        "are cut on local wall-clock time")
    parser.add_argument("--max-gap", type=int, default=3, metavar="N",
                        help="fill interior gaps of at most N empty buckets "
                        "by linear interpolation; 0 disables filling "
                        "(default: 3)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    points = load_csv(args.input)
    records = resample(
        points,
        freq=args.freq,
        closed=args.closed,
        label=args.label,
        agg=args.agg,
        timezone_name=args.tz,
        max_gap=args.max_gap,
    )
    summary = summarize(len(points), records)
    if args.out:
        write_report(records, summary, args.out)
    print(summary_line(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
