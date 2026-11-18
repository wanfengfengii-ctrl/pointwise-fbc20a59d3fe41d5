from collections.abc import Iterable
from dataclasses import dataclass
from sqlite3 import Connection

from intake.identity import RevisionKey
from planning.inventory import load_inventory
from planning.recovery import resolve_coverage
from planning.target import RecoveryTarget, resolve_target
from retention.catalog import RollupRef


class UnrecoverableTarget(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RecoveryTerm:
    rollup: RollupRef


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    target: RecoveryTarget
    terms: tuple[RecoveryTerm, ...]


def build_plan(
    connection: Connection, key: RevisionKey, sections: Iterable[str]
) -> RecoveryPlan:
    target = resolve_target(connection, key, sections)
    inventory = load_inventory(connection, target)
    rollups = resolve_coverage(target, inventory)
    if rollups is None:
        raise UnrecoverableTarget(f"cannot recover {target.sections!r} from {key}")
    return RecoveryPlan(target, tuple(RecoveryTerm(ref) for ref in rollups))
