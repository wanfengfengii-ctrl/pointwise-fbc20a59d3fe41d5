from collections.abc import Sequence

from planning.target import RecoveryTarget
from retention.catalog import RollupRef


def resolve_coverage(
    target: RecoveryTarget, inventory: Sequence[RollupRef]
) -> tuple[RollupRef, ...] | None:
    for ref in inventory:
        if ref.coverage.sections == target.sections:
            return (ref,)

    requested = set(target.sections)
    selected = tuple(ref for ref in inventory if requested.issuperset(ref.coverage.sections))
    covered = {section for ref in selected for section in ref.coverage.sections}
    if covered != requested:
        return None
    return selected
