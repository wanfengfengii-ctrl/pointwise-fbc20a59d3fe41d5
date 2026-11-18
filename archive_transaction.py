from collections.abc import Iterator
from contextlib import contextmanager
from sqlite3 import Connection


@contextmanager
def transaction(connection: Connection, *, write: bool) -> Iterator[None]:
    if connection.in_transaction:
        raise RuntimeError('archive operation requires an idle connection')
    connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
    try:
        yield
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
