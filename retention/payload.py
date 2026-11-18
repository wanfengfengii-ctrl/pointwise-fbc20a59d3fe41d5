from collections.abc import Sequence
from sqlite3 import Connection

from amounts import decode_cents, encode_cents
from retention.catalog import RollupRef
from retention.rollup import RollupMeasure


class IncompleteRollup(ValueError):
    pass


def init_rollup_payloads(connection: Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS rollup_payloads (
            batch_day TEXT NOT NULL,
            revision TEXT NOT NULL,
            rollup_id INTEGER NOT NULL,
            crew TEXT NOT NULL,
            row_count INTEGER NOT NULL CHECK (row_count > 0),
            non_null_count INTEGER NOT NULL CHECK (non_null_count BETWEEN 0 AND row_count),
            amount_cents TEXT NOT NULL,
            PRIMARY KEY (batch_day, revision, rollup_id, crew),
            FOREIGN KEY (batch_day, revision, rollup_id)
                REFERENCES rollup_catalog (batch_day, revision, rollup_id)
        )
    ''')


def write_rollup_payload(
    connection: Connection, ref: RollupRef, measures: Sequence[RollupMeasure]
) -> None:
    connection.executemany('''
        INSERT INTO rollup_payloads
            (batch_day, revision, rollup_id, crew, row_count, non_null_count, amount_cents)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        (*ref.revision.sql_key(), ref.number, measure.crew, measure.row_count,
         measure.non_null_count, encode_cents(measure.amount_cents))
        for measure in measures
    ))


def load_rollup_payload(connection: Connection, ref: RollupRef) -> tuple[RollupMeasure, ...]:
    rows = connection.execute('''
        SELECT crew, row_count, non_null_count, amount_cents FROM rollup_payloads
        WHERE batch_day = ? AND revision = ? AND rollup_id = ? ORDER BY crew
    ''', (*ref.revision.sql_key(), ref.number)).fetchall()
    if len(rows) != ref.crew_count:
        raise IncompleteRollup(f'incomplete payload for rollup {ref.number}')
    try:
        return tuple(
            RollupMeasure(crew, count, non_null, decode_cents(amount))
            for crew, count, non_null, amount in rows
        )
    except (TypeError, ValueError) as error:
        raise IncompleteRollup(f'invalid payload for rollup {ref.number}') from error
