"""Aggregation functions applied to the values inside one bucket."""


def _sum(values):
    return sum(values)


def _mean(values):
    return sum(values) / len(values)


def _min(values):
    return min(values)


def _max(values):
    return max(values)


def _count(values):
    return len(values)


def _last(values):
    return values[-1]


AGGREGATIONS = {
    "sum": _sum,
    "mean": _mean,
    "min": _min,
    "max": _max,
    "count": _count,
    "last": _last,
}


def aggregate(name, values):
    """Aggregate a bucket's values; empty buckets yield None, never zero."""
    if name not in AGGREGATIONS:
        raise ValueError(
            "unsupported aggregation %r (choose from %s)"
            % (name, ", ".join(sorted(AGGREGATIONS)))
        )
    if not values:
        return None
    return AGGREGATIONS[name](values)
