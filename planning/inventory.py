from sqlite3 import Connection

from planning.target import RecoveryTarget
from retention.catalog import RollupRef, list_rollups


def load_inventory(connection: Connection, target: RecoveryTarget) -> tuple[RollupRef, ...]:
    # The complete revision directory includes inputs that cancel outside the target.
    return list_rollups(connection, target.revision)
