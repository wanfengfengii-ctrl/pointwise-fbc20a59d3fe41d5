from datetime import timedelta
from sqlite3 import IntegrityError

from intake.revisions import RevisionNotFrozen, get_revision
from intake.rows import SourceRow, iter_source_rows
from retention.expiry import ExpiryResult, NotDue, RetentionUnavailable, expire
from retention.lifecycle import get_retention
from retention.rollup import RollupMeasure
from retention.seal import seal
from support import ArchiveCase, DUE, PAIR_ROWS, PAIR_SCOPES


class RetentionTests(ArchiveCase):
    def test_early_expiry(self):
        key = self.stage_rows(PAIR_ROWS)
        with self.assertRaises(RevisionNotFrozen):
            expire(self.db, key, DUE)
        seal(self.db, key, PAIR_SCOPES)
        retained = self.retained(key)
        with self.assertRaises(NotDue):
            expire(self.db, key, DUE - timedelta(days=1))
        self.assertEqual(tuple(iter_source_rows(self.db, key)), PAIR_ROWS)
        self.assertEqual(self.retained(key), retained)
        self.assertIsNone(get_retention(self.db, key).expired_on)

    def test_expiry_repeat(self):
        key = self.stage_rows(PAIR_ROWS)
        seal(self.db, key, PAIR_SCOPES)
        retained = self.retained(key)
        frozen = get_revision(self.db, key)
        self.assertEqual(expire(self.db, key, DUE), ExpiryResult.EXPIRED)
        self.assertEqual(tuple(iter_source_rows(self.db, key)), ())
        self.assertEqual(expire(self.db, key, DUE + timedelta(days=1)), ExpiryResult.ALREADY_EXPIRED)
        self.assertEqual(self.retained(key), retained)
        self.assertEqual(get_revision(self.db, key), frozen)
        self.assertEqual(get_retention(self.db, key).expired_on, DUE)

    def test_sibling_revision(self):
        old = self.stage_rows(PAIR_ROWS)
        seal(self.db, old, PAIR_SCOPES)
        correction = (SourceRow('a', 'A', 'crew', 75),)
        newer = self.stage_rows(correction, 'r2')
        self.assertEqual(expire(self.db, old, DUE), ExpiryResult.EXPIRED)
        self.assertEqual(tuple(iter_source_rows(self.db, old)), ())
        self.assertEqual(tuple(iter_source_rows(self.db, newer)), correction)
        self.assertIsNone(get_retention(self.db, newer))
        self.assertEqual(self.retained(old)[('A', 'B')], (RollupMeasure('crew', 2, 2, 14),))
        seal(self.db, newer, [('A',)])
        self.assertEqual(self.retained(newer)[('A',)], (RollupMeasure('crew', 1, 1, 75),))

    def test_missing_payload_prevents_expiry(self):
        key = self.stage_rows(PAIR_ROWS)
        first, *_ = seal(self.db, key, PAIR_SCOPES)
        self.db.execute('DELETE FROM rollup_payloads WHERE rollup_id = ?', (first.number,))
        with self.assertRaises(RetentionUnavailable):
            expire(self.db, key, DUE)
        self.assertEqual(tuple(iter_source_rows(self.db, key)), PAIR_ROWS)
        self.assertIsNone(get_retention(self.db, key).expired_on)

    def test_expiry_update_failure_restores_source_rows(self):
        key = self.stage_rows(PAIR_ROWS)
        seal(self.db, key, PAIR_SCOPES)
        self.db.execute('''
            CREATE TEMP TRIGGER refuse_expiry BEFORE UPDATE OF expired_on ON retention_schedule
            WHEN NOT EXISTS (SELECT 1 FROM source_rows
                             WHERE batch_day = NEW.batch_day AND revision = NEW.revision)
            BEGIN
                SELECT RAISE(ABORT, 'expiry audit write failed');
            END
        ''')
        with self.assertRaisesRegex(IntegrityError, 'expiry audit write failed'):
            expire(self.db, key, DUE)
        self.assertEqual(tuple(iter_source_rows(self.db, key)), PAIR_ROWS)
        self.assertIsNone(get_retention(self.db, key).expired_on)
        self.db.execute('DROP TRIGGER refuse_expiry')
        self.assertEqual(expire(self.db, key, DUE), ExpiryResult.EXPIRED)
