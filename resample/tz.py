"""Timezone helpers: parse timestamps, normalize to UTC, local wall-clock math."""

from datetime import date, datetime, timedelta, timezone, tzinfo


def parse_timestamp(text):
    """Parse an ISO-8601 timestamp; naive input is assumed to be UTC.

    Always returns an aware datetime in UTC.
    """
    text = text.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_timezone(name):
    """Resolve a timezone name to a tzinfo (prefers IANA data via zoneinfo)."""
    if name is None:
        return None
    if name.upper() in ("UTC", "Z", "+00:00"):
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        if name == "Europe/Berlin":
            return BerlinTime()
        raise


def to_wall(dt_utc, tzinfo_):
    """Convert an aware UTC datetime to a naive local wall-clock datetime."""
    if tzinfo_ is None:
        return dt_utc.replace(tzinfo=None)
    return dt_utc.astimezone(tzinfo_).replace(tzinfo=None)


def localize(wall_naive, tzinfo_):
    """Attach a timezone to a naive wall-clock datetime (first occurrence)."""
    if tzinfo_ is None:
        return wall_naive.replace(tzinfo=timezone.utc)
    return wall_naive.replace(tzinfo=tzinfo_, fold=0)


def _last_sunday(year, month):
    d = date(year, month, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


class BerlinTime(tzinfo):
    """Fallback Europe/Berlin tzinfo (EU DST rules) when IANA data is missing.

    DST: UTC+2 from the last Sunday of March 01:00 UTC until the last
    Sunday of October 01:00 UTC, otherwise UTC+1.
    """

    _STD = timedelta(hours=1)
    _DST = timedelta(hours=2)

    @staticmethod
    def _transitions(year):
        start = datetime(year, 3, _last_sunday(year, 3).day, 1, 0)
        end = datetime(year, 10, _last_sunday(year, 10).day, 1, 0)
        return start, end

    def utcoffset(self, dt):
        if dt is None:
            return self._STD
        wall = dt.replace(tzinfo=None)
        start, end = self._transitions(wall.year)
        as_std = wall - self._STD
        as_dst = wall - self._DST
        dst_valid = start <= as_dst < end
        std_valid = not (start <= as_std < end)
        if dst_valid and std_valid:
            return self._STD if dt.fold else self._DST
        if dst_valid:
            return self._DST
        if std_valid:
            return self._STD
        return self._STD if dt.fold else self._DST

    def dst(self, dt):
        if dt is None:
            return timedelta(0)
        return self.utcoffset(dt) - self._STD

    def tzname(self, dt):
        return "CEST" if self.dst(dt) else "CET"

    def fromutc(self, dt):
        utc = dt.replace(tzinfo=None)
        start, end = self._transitions(utc.year)
        if start <= utc < end:
            wall = utc + self._DST
        else:
            wall = utc + self._STD
        fold = 1 if end <= utc < end + self._STD else 0
        return wall.replace(tzinfo=self, fold=fold)
