from dataclasses import dataclass
from datetime import date, timedelta
from sqlite3 import Connection

from intake.identity import RevisionKey


RETENTION_DAYS = 7


@dataclass(frozen=True, slots=True)
class RetentionSchedule:
    due_on: date
    rollup_count: int
    expired_on: date | None = None

    def is_due(self, on: date) -> bool:
        return on >= self.due_on


def init_retention(connection: Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS retention_schedule (
            batch_day TEXT NOT NULL,
            revision TEXT NOT NULL,
            due_on TEXT NOT NULL,
            rollup_count INTEGER NOT NULL CHECK (rollup_count > 0),
            expired_on TEXT CHECK (expired_on IS NULL OR expired_on >= due_on),
            PRIMARY KEY (batch_day, revision),
            FOREIGN KEY (batch_day, revision) REFERENCES revisions (batch_day, revision)
        )
    ''')


def record_retention(connection: Connection, key: RevisionKey, rollup_count: int) -> None:
    try:
        due_on = key.batch_day + timedelta(days=RETENTION_DAYS)
    except OverflowError as error:
        raise ValueError('batch date is too late to schedule retention') from error
    connection.execute('''
        INSERT INTO retention_schedule (batch_day, revision, due_on, rollup_count)
        VALUES (?, ?, ?, ?)
    ''', (*key.sql_key(), due_on.isoformat(), rollup_count))


def get_retention(connection: Connection, key: RevisionKey) -> RetentionSchedule | None:
    row = connection.execute('''
        SELECT due_on, rollup_count, expired_on FROM retention_schedule
        WHERE batch_day = ? AND revision = ?
    ''', key.sql_key()).fetchone()
    if row is None:
        return None
    due_on, rollup_count, expired_on = row
    return RetentionSchedule(
        date.fromisoformat(due_on), rollup_count,
        None if expired_on is None else date.fromisoformat(expired_on),
    )


def mark_expired(connection: Connection, key: RevisionKey, on: date) -> None:
    connection.execute('''
        UPDATE retention_schedule SET expired_on = ?
        WHERE batch_day = ? AND revision = ? AND expired_on IS NULL
    ''', (on.isoformat(), *key.sql_key()))
