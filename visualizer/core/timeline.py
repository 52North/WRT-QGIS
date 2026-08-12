"""The absolute-UTC clock shared by the route and the weather dataset.

This takes the union of both datasets' timestamps and steps through them in order.
Each dataset then resolves independently to its nearest entry at or before the current time.
"""

from bisect import bisect_right

ROUTE = "route"
WEATHER = "weather"


def _msecs(stamp):
    return stamp.toMSecsSinceEpoch()


class Timeline:
    def __init__(self):
        self._stamps = {ROUTE: [], WEATHER: []}
        self._steps = []
        self._step_msecs = []

    # input

    def set_stamps(self, kind, stamps):
        """Register one dataset's absolute timestamps; invalid ones are dropped."""
        self._stamps[kind] = [s for s in stamps if s.isValid()]
        self._rebuild()

    def clear(self, kind):
        self._stamps[kind] = []
        self._rebuild()

    def _rebuild(self):
        merged = {}
        for stamps in self._stamps.values():
            for stamp in stamps:
                merged.setdefault(_msecs(stamp), stamp)
        self._step_msecs = sorted(merged)
        self._steps = [merged[ms] for ms in self._step_msecs]

    # output

    @property
    def steps(self):
        return self._steps

    @property
    def is_empty(self):
        return not self._steps

    def count(self, kind):
        return len(self._stamps[kind])

    def has(self, kind):
        return bool(self._stamps[kind])

    def bounds(self, kind):
        """First and last stamp of one dataset, or None when it is not loaded."""
        stamps = self._stamps[kind]
        return (stamps[0], stamps[-1]) if stamps else None

    @property
    def span(self):
        """First and last step overall, or None when nothing is loaded."""
        return (self._steps[0], self._steps[-1]) if self._steps else None

    def index_at(self, kind, stamp):
        """Index of the newest entry of ``kind`` at or before ``stamp``.

        None when the dataset is absent or ``stamp`` precedes its first entry —
        that leading gap is what the timeline bar hatches.
        """
        stamps = self._stamps[kind]
        if not stamps:
            return None
        pos = bisect_right([_msecs(s) for s in stamps], _msecs(stamp)) - 1
        return pos if pos >= 0 else None

    def step_at(self, stamp):
        """Index into ``steps`` of the newest step at or before ``stamp``."""
        if not self._steps:
            return None
        pos = bisect_right(self._step_msecs, _msecs(stamp)) - 1
        return max(pos, 0)

    # drawing

    def fraction(self, stamp):
        """Position of ``stamp`` along the full span, clamped to 0..1."""
        if not self._steps:
            return 0.0
        start, end = self._step_msecs[0], self._step_msecs[-1]
        if end <= start:
            return 0.0
        return min(max((_msecs(stamp) - start) / (end - start), 0.0), 1.0)

    def step_fraction(self, index):
        if not self._steps:
            return 0.0
        index = min(max(index, 0), len(self._steps) - 1)
        return self.fraction(self._steps[index])

    def coverage(self, kind):
        """(start, end) fractions of one dataset's extent, or None if absent."""
        bounds = self.bounds(kind)
        if bounds is None:
            return None
        return self.fraction(bounds[0]), self.fraction(bounds[1])

    def tick_fractions(self, kind):
        return [self.fraction(stamp) for stamp in self._stamps[kind]]

    def axis_labels(self, count=5):
        """``count`` stamps spread evenly across the span, for the date axis."""
        if not self._steps:
            return []
        start, end = self._steps[0], self._steps[-1]
        if count < 2 or end <= start:
            return [start]
        total = start.secsTo(end)
        return [start.addSecs(round(total * i / (count - 1))) for i in range(count)]

    def day_of(self, stamp):
        """1-based day number of ``stamp`` within the span, and the span's day count."""
        if not self._steps:
            return (0, 0)
        start, end = self._steps[0], self._steps[-1]
        total = start.date().daysTo(end.date()) + 1
        return (start.date().daysTo(stamp.date()) + 1, total)

    def dates(self):
        """Distinct calendar dates covered by ``steps``, in order."""
        result = []
        seen_days = set()
        for stamp in self._steps:
            date = stamp.date()
            julian = date.toJulianDay()
            if julian not in seen_days:
                seen_days.add(julian)
                result.append(date)
        return result

    def indices_on_date(self, date):
        """Indices into ``steps`` whose stamp falls on ``date``, in order."""
        julian = date.toJulianDay()
        return [i for i, stamp in enumerate(self._steps) if stamp.date().toJulianDay() == julian]
