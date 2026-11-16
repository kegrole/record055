"""Gap filling via linear interpolation.

Only interior gaps (null runs bounded on both sides by real values) are
filled, and only when the gap is no longer than max_gap buckets. Leading
and trailing null runs are never touched: no extrapolation.
"""


def linear_fill(records, max_gap):
    """Fill interior null runs of length <= max_gap in place.

    records: list of dicts with a 'value' key (None for empty buckets).
    Filled entries get 'filled' set to True. Returns the number filled.
    """
    if max_gap < 0:
        raise ValueError("max_gap must be >= 0")
    filled = 0
    n = len(records)
    i = 0
    while i < n:
        if records[i]["value"] is not None:
            i += 1
            continue
        j = i
        while j < n and records[j]["value"] is None:
            j += 1
        gap = j - i
        interior = i > 0 and j < n
        if interior and gap <= max_gap:
            v0 = records[i - 1]["value"]
            v1 = records[j]["value"]
            for k in range(gap):
                frac = (k + 1) / (gap + 1)
                records[i + k]["value"] = v0 + (v1 - v0) * frac
                records[i + k]["filled"] = True
                filled += 1
        i = j
    return filled
