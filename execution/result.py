from dataclasses import dataclass
from sqlite3 import Connection

from execution.combine import combine_measures
from execution.input import read_plan_inputs
from execution.measures import ReportRow, finalize_measures
from intake.identity import RevisionKey
from planning.plan import RecoveryPlan


@dataclass(frozen=True, slots=True)
class ReissueResult:
    revision: RevisionKey
    sections: tuple[str, ...]
    rows: tuple[ReportRow, ...]


def execute_plan(connection: Connection, plan: RecoveryPlan) -> ReissueResult:
    totals = combine_measures(read_plan_inputs(connection, plan))
    rows = []
    for crew in sorted(totals):
        row = finalize_measures(crew, totals[crew])
        if row is not None:
            rows.append(row)
    return ReissueResult(plan.target.revision, plan.target.sections, tuple(rows))
