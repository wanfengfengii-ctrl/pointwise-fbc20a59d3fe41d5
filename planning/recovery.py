from collections.abc import Sequence
from fractions import Fraction

from planning.target import RecoveryTarget
from retention.catalog import RollupRef


def resolve_coverage(
    target: RecoveryTarget, inventory: Sequence[RollupRef]
) -> tuple[tuple[RollupRef, Fraction], ...] | None:
    # Each retained coverage is a 0/1 vector over the revision's known
    # sections. The target is recoverable only when its own vector is an
    # exact rational linear combination of the retained vectors; the
    # weights may overlap, cancel sections outside the target, or be
    # fractional. Anything less precise must be refused.
    for ref in inventory:
        if ref.coverage.sections == target.sections:
            return ((ref, Fraction(1)),)
    weights = _exact_weights(
        tuple(ref.coverage.sections for ref in inventory),
        target.known_sections,
        target.sections,
    )
    if weights is None:
        return None
    return tuple(
        (ref, weight) for ref, weight in zip(inventory, weights) if weight
    )


def _exact_weights(
    coverages: tuple[tuple[str, ...], ...],
    known: tuple[str, ...],
    wanted: tuple[str, ...],
) -> tuple[Fraction, ...] | None:
    rows = [
        [Fraction(section in coverage) for coverage in coverages]
        + [Fraction(section in wanted)]
        for section in known
    ]
    width = len(coverages)
    pivots: list[int] = []
    rank = 0
    for column in range(width):
        pivot = next(
            (row for row in range(rank, len(rows)) if rows[row][column]), None
        )
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        rows[rank] = [value / rows[rank][column] for value in rows[rank]]
        for row in range(len(rows)):
            if row != rank and rows[row][column]:
                factor = rows[row][column]
                rows[row] = [
                    value - factor * pivot_value
                    for value, pivot_value in zip(rows[row], rows[rank])
                ]
        pivots.append(column)
        rank += 1
        if rank == len(rows):
            break
    for row in rows:
        if not any(row[:width]) and row[width]:
            return None
    weights = [Fraction(0)] * width
    for row, column in enumerate(pivots):
        weights[column] = rows[row][width]
    return tuple(weights)
