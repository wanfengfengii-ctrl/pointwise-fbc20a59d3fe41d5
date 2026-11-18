from collections.abc import Iterable
from dataclasses import dataclass
from sqlite3 import Connection

from execution.measures import ReportRow
from intake.identity import RevisionKey
from reports.codec import (
    ReportHeader, decode_report_header, decode_report_row, encode_report_header, encode_report_row,
)


@dataclass(frozen=True, slots=True)
class StoredReport:
    header: ReportHeader
    rows: tuple[ReportRow, ...]


def init_report_storage(connection: Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS report_headers (
            report_id INTEGER PRIMARY KEY,
            batch_day TEXT NOT NULL,
            revision TEXT NOT NULL,
            sections TEXT NOT NULL,
            FOREIGN KEY (batch_day, revision) REFERENCES revisions (batch_day, revision)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS report_rows (
            report_id INTEGER NOT NULL,
            position INTEGER NOT NULL CHECK (position >= 0),
            crew TEXT NOT NULL,
            row_count INTEGER NOT NULL CHECK (row_count > 0),
            non_null_count INTEGER NOT NULL CHECK (non_null_count BETWEEN 0 AND row_count),
            amount_cents TEXT CHECK ((non_null_count = 0) = (amount_cents IS NULL)),
            PRIMARY KEY (report_id, position),
            UNIQUE (report_id, crew),
            FOREIGN KEY (report_id) REFERENCES report_headers (report_id)
        )
    ''')


def insert_report_header(
    connection: Connection, revision: RevisionKey, sections: tuple[str, ...]
) -> ReportHeader:
    result = connection.execute('''
        INSERT INTO report_headers (batch_day, revision, sections) VALUES (?, ?, ?)
    ''', encode_report_header(revision, sections))
    return ReportHeader(result.lastrowid, revision, sections)


def insert_report_rows(connection: Connection, number: int, rows: Iterable[ReportRow]) -> None:
    connection.executemany('''
        INSERT INTO report_rows (report_id, position, crew, row_count, non_null_count, amount_cents)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (encode_report_row(number, position, row) for position, row in enumerate(rows)))


def get_report(connection: Connection, number: int) -> StoredReport | None:
    record = connection.execute('''
        SELECT batch_day, revision, sections FROM report_headers WHERE report_id = ?
    ''', (number,)).fetchone()
    if record is None:
        return None
    header = decode_report_header(number, *record)
    rows = connection.execute('''
        SELECT crew, row_count, non_null_count, amount_cents FROM report_rows
        WHERE report_id = ? ORDER BY position
    ''', (number,))
    return StoredReport(header, tuple(decode_report_row(*row) for row in rows))
