from collections.abc import Iterable
from dataclasses import dataclass

from execution.input import ExecutionInput


@dataclass(slots=True)
class NetMeasures:
    row_count: int = 0
    non_null_count: int = 0
    amount_cents: int = 0


def combine_measures(inputs: Iterable[ExecutionInput]) -> dict[str, NetMeasures]:
    totals: dict[str, NetMeasures] = {}
    for source in inputs:
        for measure in source.measures:
            if measure.crew not in totals:
                totals[measure.crew] = NetMeasures()
            net = totals[measure.crew]
            net.row_count += measure.row_count
            net.non_null_count += measure.non_null_count
            net.amount_cents += measure.amount_cents
    return totals
