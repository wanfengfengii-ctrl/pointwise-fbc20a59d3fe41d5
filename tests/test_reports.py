from execution.measures import InvalidMeasures, ReportRow
from intake.rows import SourceRow, iter_source_rows
from reports.archive import initialize_archive
from reports.publish import PublicationError, reissue_report
from reports.read import ReportNotFound, read
from retention.expiry import ExpiryResult, expire
from retention.lifecycle import get_retention
from retention.seal import seal
from support import ArchiveCase, DUE, PAIR_ROWS, PAIR_SCOPES


class ReportTests(ArchiveCase):
    def two_crew_source(self):
        rows = (SourceRow('1', 'A', 'alpha', 5), SourceRow('2', 'A', 'beta', None))
        key = self.stage_rows(rows)
        seal(self.db, key, [('A',)])
        expire(self.db, key, DUE)
        return key

    def test_rollback(self):
        key = self.two_crew_source()
        previous = reissue_report(self.db, key, ('A',))
        self.db.execute('''
            CREATE TEMP TRIGGER refuse_report_first BEFORE INSERT ON report_rows
            WHEN NEW.position = 0 AND EXISTS (
                SELECT 1 FROM report_headers WHERE report_id = NEW.report_id
            )
            BEGIN
                SELECT RAISE(ABORT, 'first report row failed');
            END
        ''')
        with self.assertRaises(PublicationError) as raised:
            reissue_report(self.db, key, ('A',))
        self.assertIn('first report row failed', str(raised.exception.__cause__))
        self.assertEqual(self.report_counts(), (1, 2))
        self.assertEqual(read(self.db, previous.header.number), previous)

    def test_rollback_after_one_row(self):
        key = self.two_crew_source()
        previous = reissue_report(self.db, key, ('A',))
        self.db.execute('''
            CREATE TEMP TRIGGER refuse_report_second BEFORE INSERT ON report_rows
            WHEN NEW.position = 1 AND EXISTS (
                SELECT 1 FROM report_rows
                WHERE report_id = NEW.report_id AND position = 0
            )
            BEGIN
                SELECT RAISE(ABORT, 'second report row failed');
            END
        ''')
        with self.assertRaises(PublicationError) as raised:
            reissue_report(self.db, key, ('A',))
        self.assertIn('second report row failed', str(raised.exception.__cause__))
        self.assertEqual(self.report_counts(), (1, 2))
        with self.assertRaises(ReportNotFound):
            read(self.db, previous.header.number + 1)
        self.assertEqual(read(self.db, previous.header.number), previous)
        self.db.execute('DROP TRIGGER refuse_report_second')
        retry = reissue_report(self.db, key, ('A',))
        self.assertEqual(self.report_counts(), (2, 4))
        self.assertEqual(read(self.db, retry.header.number).rows, previous.rows)

    def test_invalid_net_measures_do_not_publish(self):
        key = self.stage_rows(PAIR_ROWS)
        first, *_ = seal(self.db, key, PAIR_SCOPES)
        expire(self.db, key, DUE)
        previous = reissue_report(self.db, key, ('A', 'B', 'C'))
        self.db.execute('UPDATE rollup_payloads SET amount_cents = ? WHERE rollup_id = ?', ('f', first.number))
        with self.assertRaisesRegex(InvalidMeasures, 'non-integral'):
            reissue_report(self.db, key, ('A', 'B', 'C'))
        self.assertEqual(self.report_counts(), (1, 1))
        self.assertEqual(read(self.db, previous.header.number).rows, (ReportRow('crew', 3, 3, 30),))

    def test_read_after_revision(self):
        old_key = self.two_crew_source()
        original = reissue_report(self.db, old_key, ['A'])
        new_key = self.stage_rows([
            SourceRow('1', 'A', 'alpha', 56), SourceRow('2', 'B', 'beta', 0),
        ], 'r2')
        seal(self.db, new_key, [('A', 'B')])
        expire(self.db, new_key, DUE)
        corrected = reissue_report(self.db, new_key, ['B', 'A'])
        self.db.close()
        reopened = self.open_connection()
        saved = read(reopened, original.header.number)
        self.assertEqual(saved, original)
        self.assertEqual(saved.header.revision, old_key)
        self.assertEqual(saved.header.sections, ('A',))
        self.assertEqual(saved.rows, (ReportRow('alpha', 1, 1, 5), ReportRow('beta', 1, 0, None)))
        self.assertEqual(read(reopened, corrected.header.number).rows, (
            ReportRow('alpha', 1, 1, 56), ReportRow('beta', 1, 1, 0),
        ))

    def test_unknown_number(self):
        for number in (1, 0, True, 2**63):
            with self.subTest(number=number):
                with self.assertRaises(ReportNotFound):
                    read(self.db, number)
        self.assertEqual(self.report_counts(), (0, 0))

    def test_reinitialize(self):
        old_key = self.two_crew_source()
        original = reissue_report(self.db, old_key, ('A',))
        draft_rows = (SourceRow('latest', 'A', 'alpha', 81),)
        draft = self.stage_rows(draft_rows, 'r2')
        initialize_archive(self.db)
        self.db.close()
        reopened = self.open_connection()
        initialize_archive(reopened)
        self.assertEqual(read(reopened, original.header.number), original)
        self.assertEqual(get_retention(reopened, old_key).expired_on, DUE)
        self.assertEqual(expire(reopened, old_key, DUE), ExpiryResult.ALREADY_EXPIRED)
        self.assertEqual(tuple(iter_source_rows(reopened, draft)), draft_rows)
        seal(reopened, draft, [('A',)])
        self.assertEqual(reissue_report(reopened, draft, ('A',)).rows, (ReportRow('alpha', 1, 1, 81),))

    def test_exact_integer_persistence(self):
        large = -(1 << 17000)
        key = self.stage_rows([SourceRow('large', 'A', 'crew', large), SourceRow('one', 'A', 'crew', 1)])
        seal(self.db, key, [('A',)])
        expire(self.db, key, DUE)
        issued = reissue_report(self.db, key, ('A',))
        self.db.close()
        saved = read(self.open_connection(), issued.header.number)
        result, = saved.rows
        self.assertEqual((result.row_count, result.non_null_count), (2, 2))
        self.assertIs(type(result.amount_cents), int)
        self.assertTrue(result.amount_cents == large + 1, 'integer cents changed during persistence')
