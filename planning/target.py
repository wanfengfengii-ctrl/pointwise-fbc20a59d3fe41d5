from collections.abc import Iterable
from dataclasses import dataclass
from sqlite3 import Connection

from intake.identity import RevisionKey
from intake.revisions import require_frozen
from retention.coverage import InvalidCoverage, normalize_sections


class InvalidTarget(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RecoveryTarget:
    revision: RevisionKey
    sections: tuple[str, ...]
    known_sections: tuple[str, ...]


def resolve_target(
    connection: Connection, key: RevisionKey, sections: Iterable[str]
) -> RecoveryTarget:
    revision = require_frozen(connection, key)
    try:
        canonical = normalize_sections(sections, revision.sections)
    except InvalidCoverage as error:
        raise InvalidTarget(str(error)) from error
    return RecoveryTarget(key, canonical, revision.sections)
