from collections.abc import Iterable
from datetime import date
from sqlite3 import Connection

from archive_transaction import transaction
from intake.identity import RevisionKey
from intake.revisions import RevisionRecord, register_editable_revision
from intake.rows import SourceRow, replace_source_rows
from intake.validation import validate_rows


def stage(
    connection: Connection,
    batch_day: date | str,
    revision: str,
    rows: Iterable[SourceRow],
) -> RevisionRecord:
    key = RevisionKey.from_parts(batch_day, revision)
    validated = validate_rows(rows)
    with transaction(connection, write=True):
        record = register_editable_revision(connection, key)
        replace_source_rows(connection, key, validated)
    return record
