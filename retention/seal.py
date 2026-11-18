from collections.abc import Iterable
from sqlite3 import Connection

from archive_transaction import transaction
from intake.identity import RevisionKey
from intake.revisions import FrozenRevision, RevisionState, mark_frozen, require_revision
from intake.rows import iter_source_rows
from retention.catalog import RollupRef, register_rollup
from retention.coverage import normalize_coverages
from retention.lifecycle import record_retention
from retention.payload import write_rollup_payload
from retention.rollup import compute_rollups


def seal(
    connection: Connection, key: RevisionKey, scopes: Iterable[Iterable[str]]
) -> tuple[RollupRef, ...]:
    with transaction(connection, write=True):
        revision = require_revision(connection, key)
        if revision.state == RevisionState.FROZEN:
            raise FrozenRevision(key)
        rows = tuple(iter_source_rows(connection, key))
        sections = tuple(sorted({row.section for row in rows}))
        coverages = normalize_coverages(scopes, sections)
        rollups = compute_rollups(rows, coverages)

        mark_frozen(connection, key, sections)
        record_retention(connection, key, len(coverages))
        directory = []
        for coverage in coverages:
            payload = rollups[coverage]
            ref = register_rollup(connection, key, coverage, len(payload))
            write_rollup_payload(connection, ref, payload)
            directory.append(ref)
    return tuple(directory)
