from datetime import date
from enum import StrEnum
from sqlite3 import Connection

from archive_transaction import transaction
from intake.identity import RevisionKey, business_date
from intake.revisions import require_frozen
from intake.rows import delete_source_rows
from retention.catalog import list_rollups
from retention.lifecycle import get_retention, mark_expired
from retention.payload import IncompleteRollup, load_rollup_payload


class ExpiryResult(StrEnum):
    EXPIRED = 'expired'
    ALREADY_EXPIRED = 'already_expired'


class NotDue(ValueError):
    pass


class RetentionUnavailable(ValueError):
    pass


def expire(connection: Connection, key: RevisionKey, on: date | str) -> ExpiryResult:
    requested_day = business_date(on)
    with transaction(connection, write=True):
        require_frozen(connection, key)
        schedule = get_retention(connection, key)
        if schedule is None:
            raise RetentionUnavailable(f'missing retention schedule for {key}')
        if schedule.expired_on is not None:
            return ExpiryResult.ALREADY_EXPIRED
        if not schedule.is_due(requested_day):
            raise NotDue(f'revision is due on {schedule.due_on.isoformat()}')
        directory = list_rollups(connection, key)
        if len(directory) != schedule.rollup_count:
            raise RetentionUnavailable(f'incomplete retention directory for {key}')
        try:
            for ref in directory:
                load_rollup_payload(connection, ref)
        except IncompleteRollup as error:
            raise RetentionUnavailable(f'incomplete retained payload for {key}') from error
        delete_source_rows(connection, key)
        mark_expired(connection, key, requested_day)
    return ExpiryResult.EXPIRED
