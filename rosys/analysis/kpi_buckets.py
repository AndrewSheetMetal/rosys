from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass(slots=True, kw_only=True)
class TimeBucket:
    date: str
    incidents: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_buckets(cls, sources: list[TimeBucket]) -> TimeBucket:
        counter: Counter = Counter()
        for source in sources:
            counter.update(source.incidents)
        return cls(date=sources[0].date, incidents=dict(counter))


@dataclass(slots=True, kw_only=True)
class Day(TimeBucket):
    pass


@dataclass(slots=True, kw_only=True)
class Week(TimeBucket):
    pass


@dataclass(slots=True, kw_only=True)
class Month(TimeBucket):
    pass
