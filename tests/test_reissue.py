from execution.measures import ReportRow
from intake.identity import RevisionKey
from intake.revisions import RevisionNotFrozen, UnknownRevision
from intake.rows import SourceRow, iter_source_rows
from planning.plan import UnrecoverableTarget
from planning.target import InvalidTarget
from reports.publish import reissue_report
from reports.read import read
from retention.expiry import expire
from retention.rollup import RollupMeasure
from retention.seal import seal
from support import ArchiveCase, DAY, DUE, PAIR_ROWS, PAIR_SCOPES, direct_totals


class ReissueTests(ArchiveCase):
    def test_disjoint(self):
        key = self.stage_rows(PAIR_ROWS[:2])
        seal(self.db, key, [('A',), ('B',)])
        expire(self.db, key, DUE)
        self.assertEqual(tuple(iter_source_rows(self.db, key)), ())
        result = reissue_report(self.db, key, ['B', 'A', 'A'])
        self.assertEqual(result.header.sections, ('A', 'B'))
        self.assertEqual(result.rows, (ReportRow('crew', 2, 2, 14),))
        self.assertEqual(read(self.db, result.header.number), result)

    def test_pair_totals(self):
        key = self.stage_rows(PAIR_ROWS)
        seal(self.db, key, PAIR_SCOPES)
        self.assertEqual(self.retained(key), {
            ('A', 'B'): (RollupMeasure('crew', 2, 2, 14),),
            ('A', 'C'): (RollupMeasure('crew', 2, 2, 20),),
            ('B', 'C'): (RollupMeasure('crew', 2, 2, 26),),
        })
        expected = direct_totals(tuple(iter_source_rows(self.db, key)), {'A', 'B', 'C'})
        self.assertEqual(expected, (ReportRow('crew', 3, 3, 30),))
        expire(self.db, key, DUE)
        self.assertEqual(tuple(iter_source_rows(self.db, key)), ())
        result = reissue_report(self.db, key, ['C', 'A', 'B'])
        self.assertEqual(result.rows, expected, 'REISSUE_PAIR_TOTALS: full-line accounting mismatch')
        self.assertEqual(result.header.revision, key)
        self.assertEqual(result.header.sections, ('A', 'B', 'C'))
        self.assertEqual(read(self.db, result.header.number).rows, expected)

    def test_sparse_pair_fraction_counts(self):
        rows = (
            SourceRow('1', 'A', 'north', 4), SourceRow('2', 'B', 'mid', None),
            SourceRow('3', 'C', 'south', -5),
        )
        key = self.stage_rows(rows)
        seal(self.db, key, PAIR_SCOPES)
        expected = direct_totals(tuple(iter_source_rows(self.db, key)), {'A', 'B', 'C'})
        expire(self.db, key, DUE)
        self.assertEqual(reissue_report(self.db, key, ('A', 'B', 'C')).rows, expected)

    def test_outside_cancellation(self):
        rows = (*PAIR_ROWS, SourceRow('b-null', 'B', 'only-b', None))
        key = self.stage_rows(rows)
        seal(self.db, key, [('A', 'B'), ('B', 'C'), ('B',)])
        detail = tuple(iter_source_rows(self.db, key))
        expected_full = direct_totals(detail, {'A', 'B', 'C'})
        expected_a = direct_totals(detail, {'A'})
        self.assertEqual(expected_full, (ReportRow('crew', 3, 3, 30), ReportRow('only-b', 1, 0, None)))
        self.assertEqual(expected_a, (ReportRow('crew', 1, 1, 4),))
        expire(self.db, key, DUE)
        self.assertEqual(reissue_report(self.db, key, ['A', 'B', 'C']).rows, expected_full)
        self.assertEqual(reissue_report(self.db, key, ['A']).rows, expected_a)

    def test_zero_and_null(self):
        key = self.stage_rows([
            SourceRow('a1', 'A', 'offset', 4), SourceRow('b1', 'B', 'offset', -4),
            SourceRow('a2', 'A', 'zero', 0), SourceRow('b2', 'B', 'blank', None),
        ])
        seal(self.db, key, [('A',), ('B',)])
        expire(self.db, key, DUE)
        result = reissue_report(self.db, key, ('B', 'A'))
        expected = (ReportRow('blank', 1, 0, None), ReportRow('offset', 2, 2, 0), ReportRow('zero', 1, 1, 0))
        self.assertEqual(result.rows, expected)
        self.assertEqual(read(self.db, result.header.number).rows, expected)

    def test_unavailable(self):
        key = self.stage_rows(PAIR_ROWS)
        seal(self.db, key, [('A', 'B'), ('B', 'C')])
        expire(self.db, key, DUE)
        with self.assertRaises(UnrecoverableTarget):
            reissue_report(self.db, key, ('A', 'B', 'C'))
        self.assertEqual(self.report_counts(), (0, 0))

    def test_same_retained_different_true_totals(self):
        retained = []
        true_totals = []
        for day, due, amounts in (
            ('2026-10-01', '2026-10-08', (1, 0, 1)),
            ('2026-10-02', '2026-10-09', (0, 1, 0)),
        ):
            rows = [SourceRow(section, section, 'crew', amount) for section, amount in zip('ABC', amounts)]
            key = self.stage_rows(rows, batch_day=day)
            seal(self.db, key, [('A', 'B'), ('B', 'C')])
            retained.append(self.retained(key))
            true_totals.append(direct_totals(tuple(iter_source_rows(self.db, key)), 'ABC'))
            expire(self.db, key, due)
            with self.assertRaises(UnrecoverableTarget):
                reissue_report(self.db, key, ('A', 'B', 'C'))
            self.assertEqual(self.report_counts(), (0, 0))
        self.assertEqual(retained[0], retained[1])
        self.assertEqual(true_totals, [(ReportRow('crew', 3, 3, 2),), (ReportRow('crew', 3, 3, 1),)])

    def test_retained_target_still_valid(self):
        key = self.stage_rows(PAIR_ROWS)
        seal(self.db, key, [('A', 'B'), ('B', 'C')])
        expected = direct_totals(tuple(iter_source_rows(self.db, key)), {'A', 'B'})
        expire(self.db, key, DUE)
        with self.assertRaises(UnrecoverableTarget):
            reissue_report(self.db, key, ('A', 'B', 'C'))
        result = reissue_report(self.db, key, ('B', 'A'))
        self.assertEqual(result.rows, expected)
        self.assertEqual(self.report_counts(), (1, 1))

    def test_same_revision_only(self):
        old_key = self.stage_rows(PAIR_ROWS)
        seal(self.db, old_key, [('A',), ('B',)])
        expire(self.db, old_key, DUE)
        corrected = (
            SourceRow('a', 'A', 'crew', 100), SourceRow('b', 'B', 'crew', 200),
            SourceRow('c', 'C', 'crew', 300),
        )
        new_key = self.stage_rows(corrected, 'r2')
        seal(self.db, new_key, [('A', 'B'), ('C',)])
        self.assertEqual(reissue_report(self.db, old_key, ('A', 'B')).rows, (ReportRow('crew', 2, 2, 14),))
        with self.assertRaises(UnrecoverableTarget):
            reissue_report(self.db, old_key, ('A', 'B', 'C'))
        self.assertEqual(reissue_report(self.db, new_key, ('A', 'B', 'C')).rows, (ReportRow('crew', 3, 3, 600),))
        self.assertEqual(self.report_counts(), (2, 2))

    def test_invalid_request(self):
        frozen = self.stage_rows(PAIR_ROWS)
        seal(self.db, frozen, PAIR_SCOPES)
        draft = self.stage_rows(PAIR_ROWS, 'draft')
        with self.assertRaises(RevisionNotFrozen):
            reissue_report(self.db, draft, ['A'])
        with self.assertRaises(UnknownRevision):
            reissue_report(self.db, RevisionKey.from_parts(DAY, 'missing'), ['A'])
        for target in ([], ['Z'], 'A', [None]):
            with self.subTest(target=target):
                with self.assertRaises(InvalidTarget):
                    reissue_report(self.db, frozen, target)
        self.assertEqual(self.report_counts(), (0, 0))
