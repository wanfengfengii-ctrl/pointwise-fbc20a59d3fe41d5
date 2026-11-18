from sqlite3 import Connection

from archive_transaction import transaction
from reports.storage import StoredReport, get_report


class ReportNotFound(LookupError):
    pass


def read(connection: Connection, number: int) -> StoredReport:
    if type(number) is not int or not 0 < number < 2**63:
        raise ReportNotFound(number)
    with transaction(connection, write=False):
        report = get_report(connection, number)
        if report is None:
            raise ReportNotFound(number)
    return report
