from dataclasses import dataclass

from execution.combine import NetMeasures


class InvalidMeasures(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReportRow:
    crew: str
    row_count: int
    non_null_count: int
    amount_cents: int | None


def finalize_measures(crew: str, net: NetMeasures) -> ReportRow | None:
    values = net.row_count, net.non_null_count, net.amount_cents
    if any(value.denominator != 1 for value in values):
        raise InvalidMeasures(f'non-integral net measures for crew {crew!r}')
    rows, non_null, amount = (int(value) for value in values)
    if not 0 <= non_null <= rows or (non_null == 0 and amount != 0):
        raise InvalidMeasures(f'inconsistent net measures for crew {crew!r}')
    if rows == 0:
        return None
    return ReportRow(crew, rows, non_null, amount if non_null else None)
