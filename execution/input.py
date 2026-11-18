from collections.abc import Iterator
from dataclasses import dataclass
from sqlite3 import Connection

from planning.plan import RecoveryPlan, RecoveryTerm
from retention.payload import load_rollup_payload
from retention.rollup import RollupMeasure


@dataclass(frozen=True, slots=True)
class ExecutionInput:
    term: RecoveryTerm
    measures: tuple[RollupMeasure, ...]


def read_plan_inputs(connection: Connection, plan: RecoveryPlan) -> Iterator[ExecutionInput]:
    for term in plan.terms:
        if term.rollup.revision != plan.target.revision:
            raise ValueError('plan input belongs to another revision')
        yield ExecutionInput(term, load_rollup_payload(connection, term.rollup))
