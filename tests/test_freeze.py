from sqlite3 import IntegrityError

from intake.batches import stage
from intake.identity import RevisionKey
from intake.revisions import FrozenRevision, RevisionState, UnknownRevision, get_revision
from intake.rows import SourceRow, iter_source_rows
from intake.validation import InvalidIntake
from retention.catalog import list_rollups
from retention.coverage import InvalidCoverage
from retention.lifecycle import get_retention
from retention.payload import load_rollup_payload
from retention.rollup import RollupMeasure
from retention.seal import seal
from support import ArchiveCase, DAY, DUE, PAIR_ROWS, PAIR_SCOPES


class FreezeTests(ArchiveCase):
    def test_rollup(self):
        rows = (
            SourceRow('1', 'A', 'crew', 4), SourceRow('2', 'A', 'crew', None),
            SourceRow('3', 'A', 'crew', -4),
        )
        key = self.stage_rows(rows)
        ref, = seal(self.db, key, [('A',)])
        self.assertEqual(ref.coverage.sections, ('A',))
        self.assertEqual(load_rollup_payload(self.db, ref), (RollupMeasure('crew', 3, 2, 0),))
        frozen = get_revision(self.db, key)
        self.assertEqual(frozen.state, RevisionState.FROZEN)
        self.assertEqual(frozen.sections, ('A',))
        self.assertEqual(get_retention(self.db, key).due_on, DUE)

    def test_null_vs_zero(self):
        key = self.stage_rows([
            SourceRow('z', 'A', 'zero', 0), SourceRow('n', 'A', 'null', None),
        ])
        seal(self.db, key, [('A',)])
        self.assertEqual(self.retained(key)[('A',)], (
            RollupMeasure('null', 1, 0, 0), RollupMeasure('zero', 1, 1, 0),
        ))

    def test_independent_overlaps(self):
        key = self.stage_rows(PAIR_ROWS)
        directory = seal(self.db, key, [('C', 'B'), ('C', 'A'), ('A', 'B'), ('B', 'A')])
        self.assertEqual(tuple(ref.coverage.sections for ref in directory), PAIR_SCOPES)
        self.assertEqual(self.retained(key), {
            ('A', 'B'): (RollupMeasure('crew', 2, 2, 14),),
            ('A', 'C'): (RollupMeasure('crew', 2, 2, 20),),
            ('B', 'C'): (RollupMeasure('crew', 2, 2, 26),),
        })
        self.assertEqual(tuple(iter_source_rows(self.db, key)), PAIR_ROWS)

    def test_invalid_batch(self):
        old_key = self.stage_rows(PAIR_ROWS)
        seal(self.db, old_key, [('A',)])
        old_directory = self.retained(old_key)
        invalid_key = RevisionKey.from_parts(DAY, 'invalid')
        with self.assertRaises(InvalidIntake):
            stage(self.db, DAY, 'invalid', iter([PAIR_ROWS[0], SourceRow('x', 'A', 'crew', 1.5)]))
        self.assertIsNone(get_revision(self.db, invalid_key))
        self.assertEqual(tuple(iter_source_rows(self.db, invalid_key)), ())
        with self.assertRaises(UnknownRevision):
            seal(self.db, invalid_key, [('A',)])
        self.assertEqual(self.retained(old_key), old_directory)
        self.assertEqual(tuple(iter_source_rows(self.db, old_key)), PAIR_ROWS)

    def test_invalid_replacement_preserves_draft(self):
        key = self.stage_rows(PAIR_ROWS)
        invalid_rows = (
            ('duplicate', [PAIR_ROWS[0], PAIR_ROWS[0]]),
            ('boolean', [SourceRow('x', 'A', 'crew', True)]),
            ('blank crew', [SourceRow('x', 'A', ' ', 1)]),
        )
        for case, replacement in invalid_rows:
            with self.subTest(case=case):
                with self.assertRaises(InvalidIntake):
                    stage(self.db, DAY, 'r1', replacement)
                self.assertEqual(tuple(iter_source_rows(self.db, key)), PAIR_ROWS)
        updated = (SourceRow('updated', 'D', 'crew', 80),)
        self.assertEqual(self.stage_rows(updated), key)
        self.assertEqual(tuple(iter_source_rows(self.db, key)), updated)
        seal(self.db, key, [('D',)])
        self.assertEqual(self.retained(key), {('D',): (RollupMeasure('crew', 1, 1, 80),)})

    def test_frozen_immutable(self):
        key = self.stage_rows(PAIR_ROWS)
        seal(self.db, key, PAIR_SCOPES)
        old_record = get_revision(self.db, key)
        old_payloads = self.retained(key)
        with self.assertRaises(FrozenRevision):
            stage(self.db, DAY, 'r1', [SourceRow('other', 'A', 'crew', 800)])
        with self.assertRaises(FrozenRevision):
            seal(self.db, key, [('A',)])
        self.assertEqual(get_revision(self.db, key), old_record)
        self.assertEqual(tuple(iter_source_rows(self.db, key)), PAIR_ROWS)
        self.assertEqual(self.retained(key), old_payloads)

    def test_unknown_section(self):
        key = self.stage_rows(PAIR_ROWS)
        with self.assertRaises(InvalidCoverage):
            seal(self.db, key, [('A',), ('Z',)])
        self.assert_unsealed(key)
        self.assertEqual(len(seal(self.db, key, [('A',)])), 1)

    def test_atomic_catalog(self):
        key = self.stage_rows(PAIR_ROWS)
        self.db.execute('''
            CREATE TEMP TRIGGER reject_second_rollup BEFORE INSERT ON rollup_payloads
            WHEN (SELECT COUNT(*) FROM rollup_catalog
                  WHERE batch_day = NEW.batch_day AND revision = NEW.revision) = 2
                 AND EXISTS (SELECT 1 FROM rollup_payloads
                             WHERE batch_day = NEW.batch_day AND revision = NEW.revision)
            BEGIN
                SELECT RAISE(ABORT, 'second rollup payload rejected');
            END
        ''')
        with self.assertRaisesRegex(IntegrityError, 'second rollup payload rejected'):
            seal(self.db, key, [('A',), ('B',)])
        self.assert_unsealed(key)
        self.db.execute('DROP TRIGGER reject_second_rollup')
        seal(self.db, key, [('A',), ('B',)])
        self.assertEqual(self.retained(key), {
            ('A',): (RollupMeasure('crew', 1, 1, 4),), ('B',): (RollupMeasure('crew', 1, 1, 10),),
        })

    def assert_unsealed(self, key):
        record = get_revision(self.db, key)
        self.assertEqual((record.state, record.sections), (RevisionState.EDITABLE, ()))
        self.assertEqual(list_rollups(self.db, key), ())
        self.assertIsNone(get_retention(self.db, key))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM rollup_payloads').fetchone(), (0,))
        self.assertEqual(tuple(iter_source_rows(self.db, key)), PAIR_ROWS)
