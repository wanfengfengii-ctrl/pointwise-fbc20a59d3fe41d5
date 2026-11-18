from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from sqlite3 import Connection

from amounts import decode_cents, encode_cents
from intake.identity import RevisionKey


@dataclass(frozen=True, slots=True)
class SourceRow:
    row_id: str
    section: str
    crew: str
    amount_cents: int | None


def init_source_rows(connection: Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS source_rows (
            batch_day TEXT NOT NULL,
            revision TEXT NOT NULL,
            row_id TEXT NOT NULL,
            section TEXT NOT NULL,
            crew TEXT NOT NULL,
            amount_cents TEXT,
            PRIMARY KEY (batch_day, revision, row_id),
            FOREIGN KEY (batch_day, revision) REFERENCES revisions (batch_day, revision)
        )
    ''')


def delete_source_rows(connection: Connection, key: RevisionKey) -> None:
    connection.execute('''
        DELETE FROM source_rows WHERE batch_day = ? AND revision = ?
    ''', key.sql_key())


def replace_source_rows(
    connection: Connection, key: RevisionKey, rows: Iterable[SourceRow]
) -> None:
    delete_source_rows(connection, key)
    batch_day, revision = key.sql_key()
    connection.executemany('''
        INSERT INTO source_rows (batch_day, revision, row_id, section, crew, amount_cents)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        (batch_day, revision, row.row_id, row.section, row.crew,
         None if row.amount_cents is None else encode_cents(row.amount_cents))
        for row in rows
    ))


def iter_source_rows(connection: Connection, key: RevisionKey) -> Iterator[SourceRow]:
    records = connection.execute('''
        SELECT row_id, section, crew, amount_cents FROM source_rows
        WHERE batch_day = ? AND revision = ? ORDER BY row_id
    ''', key.sql_key())
    for row_id, section, crew, amount in records:
        yield SourceRow(row_id, section, crew, None if amount is None else decode_cents(amount))
