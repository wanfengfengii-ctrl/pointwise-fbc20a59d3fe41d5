import sqlite3
from os import PathLike

from archive_transaction import transaction
from intake.revisions import init_revisions
from intake.rows import init_source_rows
from reports.storage import init_report_storage
from retention.catalog import init_catalog
from retention.lifecycle import init_retention
from retention.payload import init_rollup_payloads


def initialize_archive(connection: sqlite3.Connection) -> None:
    if connection.in_transaction:
        raise RuntimeError('archive initialization requires an idle connection')
    connection.execute('PRAGMA foreign_keys = ON')
    with transaction(connection, write=True):
        init_revisions(connection)
        init_source_rows(connection)
        init_retention(connection)
        init_catalog(connection)
        init_rollup_payloads(connection)
        init_report_storage(connection)


def open_archive(path: str | PathLike[str]) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        initialize_archive(connection)
    except BaseException:
        connection.close()
        raise
    return connection
