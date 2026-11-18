import json
from dataclasses import dataclass
from enum import StrEnum
from sqlite3 import Connection

from intake.identity import RevisionKey


class RevisionState(StrEnum):
    EDITABLE = 'editable'
    FROZEN = 'frozen'


class UnknownRevision(LookupError):
    pass


class FrozenRevision(ValueError):
    pass


class RevisionNotFrozen(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RevisionRecord:
    key: RevisionKey
    state: RevisionState
    sections: tuple[str, ...]


def init_revisions(connection: Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS revisions (
            batch_day TEXT NOT NULL,
            revision TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('editable', 'frozen')),
            sections TEXT NOT NULL,
            PRIMARY KEY (batch_day, revision)
        )
    ''')


def get_revision(connection: Connection, key: RevisionKey) -> RevisionRecord | None:
    row = connection.execute('''
        SELECT state, sections FROM revisions WHERE batch_day = ? AND revision = ?
    ''', key.sql_key()).fetchone()
    if row is None:
        return None
    return RevisionRecord(key, RevisionState(row[0]), tuple(json.loads(row[1])))


def require_revision(connection: Connection, key: RevisionKey) -> RevisionRecord:
    record = get_revision(connection, key)
    if record is None:
        raise UnknownRevision(key)
    return record


def require_frozen(connection: Connection, key: RevisionKey) -> RevisionRecord:
    record = require_revision(connection, key)
    if record.state != RevisionState.FROZEN:
        raise RevisionNotFrozen(key)
    return record


def register_editable_revision(connection: Connection, key: RevisionKey) -> RevisionRecord:
    existing = get_revision(connection, key)
    if existing is not None:
        if existing.state == RevisionState.FROZEN:
            raise FrozenRevision(key)
        return existing
    connection.execute('''
        INSERT INTO revisions (batch_day, revision, state, sections)
        VALUES (?, ?, 'editable', '[]')
    ''', key.sql_key())
    return RevisionRecord(key, RevisionState.EDITABLE, ())


def mark_frozen(connection: Connection, key: RevisionKey, sections: tuple[str, ...]) -> None:
    updated = connection.execute('''
        UPDATE revisions SET state = 'frozen', sections = ?
        WHERE batch_day = ? AND revision = ? AND state = 'editable'
    ''', (json.dumps(sections), *key.sql_key()))
    if updated.rowcount != 1:
        raise FrozenRevision(key)
