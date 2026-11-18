from collections.abc import Iterable
from sqlite3 import Connection, Error

from archive_transaction import transaction
from execution.result import execute_plan
from intake.identity import RevisionKey
from planning.plan import build_plan
from reports.storage import StoredReport, insert_report_header, insert_report_rows


class PublicationError(RuntimeError):
    pass


def reissue_report(
    connection: Connection, key: RevisionKey, sections: Iterable[str]
) -> StoredReport:
    try:
        with transaction(connection, write=True):
            plan = build_plan(connection, key, sections)
            result = execute_plan(connection, plan)
            header = insert_report_header(connection, result.revision, result.sections)
            insert_report_rows(connection, header.number, result.rows)
    except Error as error:
        raise PublicationError(f'report transaction failed for {key}') from error
    return StoredReport(header, result.rows)
