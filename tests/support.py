import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from execution.measures import ReportRow
from intake.batches import stage
from intake.rows import SourceRow
from reports.archive import open_archive
from retention.catalog import list_rollups
from retention.payload import load_rollup_payload


DAY = '2026-10-01'
DUE = date(2026, 10, 8)
PAIR_ROWS = (
    SourceRow('a', 'A', 'crew', 4),
    SourceRow('b', 'B', 'crew', 10),
    SourceRow('c', 'C', 'crew', 16),
)
PAIR_SCOPES = (('A', 'B'), ('A', 'C'), ('B', 'C'))


def direct_totals(rows, sections):
    selected = [row for row in rows if row.section in sections]
    result = []
    for crew in sorted({row.crew for row in selected}):
        crew_rows = [row for row in selected if row.crew == crew]
        amounts = [row.amount_cents for row in crew_rows if row.amount_cents is not None]
        result.append(ReportRow(crew, len(crew_rows), len(amounts), sum(amounts) if amounts else None))
    return tuple(result)


class ArchiveCase(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'archive.sqlite3'
        self.db = self.open_connection()

    def open_connection(self):
        connection = open_archive(self.path)
        self.addCleanup(connection.close)
        return connection

    def stage_rows(self, rows, revision='r1', batch_day=DAY):
        return stage(self.db, batch_day, revision, rows).key

    def retained(self, key):
        return {
            ref.coverage.sections: load_rollup_payload(self.db, ref)
            for ref in list_rollups(self.db, key)
        }

    def report_counts(self):
        return self.db.execute('''
            SELECT (SELECT COUNT(*) FROM report_headers), (SELECT COUNT(*) FROM report_rows)
        ''').fetchone()
