import json
from dataclasses import dataclass

from amounts import decode_cents, encode_cents
from execution.measures import ReportRow
from intake.identity import RevisionKey


@dataclass(frozen=True, slots=True)
class ReportHeader:
    number: int
    revision: RevisionKey
    sections: tuple[str, ...]


def encode_report_header(
    revision: RevisionKey, sections: tuple[str, ...]
) -> tuple[str, str, str]:
    return (*revision.sql_key(), json.dumps(sections))


def decode_report_header(number: int, day: str, revision: str, sections: str) -> ReportHeader:
    return ReportHeader(number, RevisionKey.from_parts(day, revision), tuple(json.loads(sections)))


def encode_report_row(
    number: int, position: int, row: ReportRow
) -> tuple[int, int, str, int, int, str | None]:
    amount = None if row.amount_cents is None else encode_cents(row.amount_cents)
    return number, position, row.crew, row.row_count, row.non_null_count, amount


def decode_report_row(crew: str, count: int, non_null: int, amount: str | None) -> ReportRow:
    return ReportRow(crew, count, non_null, None if amount is None else decode_cents(amount))
