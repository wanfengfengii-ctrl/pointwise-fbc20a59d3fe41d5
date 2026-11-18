import json
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from intake.batches import stage
from intake.rows import SourceRow, iter_source_rows
from reports.archive import open_archive
from reports.publish import reissue_report
from reports.read import read
from retention.expiry import ExpiryResult, expire
from retention.payload import load_rollup_payload
from retention.seal import seal


def check(actual, expected, label):
    if actual != expected:
        raise RuntimeError(f'{label}: expected {expected!r}, got {actual!r}')


def main():
    sample_path = Path(__file__).resolve().parent / 'samples' / 'rail_day.json'
    sample = json.loads(sample_path.read_text(encoding='utf-8'))
    expected = {
        'retained': [
            {'sections': ['A', 'B'], 'crew': '甲班', 'row_count': 2, 'non_null_count': 2, 'amount_cents': 14},
            {'sections': ['A', 'C'], 'crew': '甲班', 'row_count': 2, 'non_null_count': 2, 'amount_cents': 20},
            {'sections': ['B', 'C'], 'crew': '甲班', 'row_count': 2, 'non_null_count': 2, 'amount_cents': 26},
        ],
        'source_rows_after_expiry': 0,
    }
    expected_report = {
        'number': 1, 'batch_day': '2026-10-01', 'revision': 'r1', 'sections': ['A', 'B', 'C'],
        'rows': [{'crew': '甲班', 'row_count': 3, 'non_null_count': 3, 'amount_cents': 30}],
    }
    with TemporaryDirectory() as temporary:
        database = Path(temporary) / 'demo.sqlite3'
        with closing(open_archive(database)) as connection:
            revision = stage(
                connection, sample['batch_day'], sample['first_revision'],
                (SourceRow(**row) for row in sample['rows']),
            )
            directory = seal(connection, revision.key, sample['coverages'])
            retained = [
                {'sections': list(ref.coverage.sections), **asdict(measure)}
                for ref in directory for measure in load_rollup_payload(connection, ref)
            ]
            check(expire(connection, revision.key, sample['expiry_day']), ExpiryResult.EXPIRED, 'source expiry')
            actual = {
                'retained': retained,
                'source_rows_after_expiry': sum(1 for _ in iter_source_rows(connection, revision.key)),
            }
            check(actual, expected, 'frozen evidence')
            report = reissue_report(connection, revision.key, sample['target'])
            check([asdict(row) for row in report.rows], expected_report['rows'], 'REISSUE_PAIR_TOTALS')
            correction = stage(
                connection, sample['batch_day'], sample['correction_revision'],
                (SourceRow(**row) for row in sample['correction_rows']),
            )
            seal(connection, correction.key, [sample['target']])
        with closing(open_archive(database)) as connection:
            saved = read(connection, report.header.number)
        downstream = {
            'number': saved.header.number,
            'batch_day': saved.header.revision.batch_day.isoformat(),
            'revision': saved.header.revision.revision,
            'sections': list(saved.header.sections),
            'rows': [asdict(row) for row in saved.rows],
        }
        check(downstream, expected_report, 'fixed report after correction and reopen')

    event = {
        'case_id': 'overlap', 'input': sample, 'expected': expected, 'actual': actual,
        'downstream_expected': expected_report, 'downstream_actual': downstream,
        'code_paths': [
            'retention/seal.py', 'retention/rollup.py', 'retention/expiry.py',
            'planning/plan.py', 'planning/recovery.py', 'execution/combine.py',
            'execution/measures.py', 'reports/publish.py', 'reports/read.py',
        ],
        'oracle': '逐份用对应的两条原始账项手算金额。全线直接数三条源行并相加 4 + 10 + 16。',
    }
    print('POINTWISE_SCENARIO ' + json.dumps(event, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
