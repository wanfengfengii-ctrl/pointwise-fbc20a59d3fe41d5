from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from intake.rows import SourceRow
from retention.coverage import Coverage


@dataclass(frozen=True, slots=True)
class RollupMeasure:
    crew: str
    row_count: int
    non_null_count: int
    amount_cents: int


def compute_rollups(
    rows: Iterable[SourceRow], coverages: Sequence[Coverage]
) -> dict[Coverage, tuple[RollupMeasure, ...]]:
    by_section: dict[str, list[Coverage]] = {}
    totals: dict[Coverage, dict[str, RollupMeasure]] = {}
    for coverage in coverages:
        totals[coverage] = {}
        for section in coverage.sections:
            by_section.setdefault(section, []).append(coverage)

    for row in rows:
        for coverage in by_section.get(row.section, ()):
            crews = totals[coverage]
            previous = crews.get(row.crew, RollupMeasure(row.crew, 0, 0, 0))
            amount = row.amount_cents
            crews[row.crew] = RollupMeasure(
                row.crew,
                previous.row_count + 1,
                previous.non_null_count + (amount is not None),
                previous.amount_cents + (0 if amount is None else amount),
            )
    return {
        coverage: tuple(crews[crew] for crew in sorted(crews))
        for coverage, crews in totals.items()
    }
