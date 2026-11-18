from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from execution.input import ExecutionInput


@dataclass(slots=True)
class NetMeasures:
    row_count: Fraction = Fraction(0)
    non_null_count: Fraction = Fraction(0)
    amount_cents: Fraction = Fraction(0)


def combine_measures(inputs: Iterable[ExecutionInput]) -> dict[str, NetMeasures]:
    totals: dict[str, NetMeasures] = {}
    for source in inputs:
        weight = source.term.weight
        for measure in source.measures:
            if measure.crew not in totals:
                totals[measure.crew] = NetMeasures()
            net = totals[measure.crew]
            net.row_count += weight * measure.row_count
            net.non_null_count += weight * measure.non_null_count
            net.amount_cents += weight * measure.amount_cents
    return totals
