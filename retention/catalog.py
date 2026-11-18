import json
from dataclasses import dataclass
from sqlite3 import Connection

from intake.identity import RevisionKey
from retention.coverage import Coverage


@dataclass(frozen=True, slots=True)
class RollupRef:
    revision: RevisionKey
    number: int
    coverage: Coverage
    crew_count: int


def init_catalog(connection: Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS rollup_catalog (
            rollup_id INTEGER PRIMARY KEY,
            batch_day TEXT NOT NULL,
            revision TEXT NOT NULL,
            sections TEXT NOT NULL,
            crew_count INTEGER NOT NULL CHECK (crew_count > 0),
            UNIQUE (batch_day, revision, sections),
            UNIQUE (batch_day, revision, rollup_id),
            FOREIGN KEY (batch_day, revision) REFERENCES revisions (batch_day, revision)
        )
    ''')


def register_rollup(
    connection: Connection, key: RevisionKey, coverage: Coverage, crew_count: int
) -> RollupRef:
    result = connection.execute('''
        INSERT INTO rollup_catalog (batch_day, revision, sections, crew_count)
        VALUES (?, ?, ?, ?)
    ''', (*key.sql_key(), json.dumps(coverage.sections), crew_count))
    return RollupRef(key, result.lastrowid, coverage, crew_count)


def list_rollups(connection: Connection, key: RevisionKey) -> tuple[RollupRef, ...]:
    rows = connection.execute('''
        SELECT rollup_id, sections, crew_count FROM rollup_catalog
        WHERE batch_day = ? AND revision = ? ORDER BY rollup_id
    ''', key.sql_key())
    return tuple(
        RollupRef(key, number, Coverage(tuple(json.loads(sections))), crew_count)
        for number, sections, crew_count in rows
    )
