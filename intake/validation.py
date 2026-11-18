from collections.abc import Iterable

from intake.identity import is_identifier
from intake.rows import SourceRow


class InvalidIntake(ValueError):
    pass


def validate_rows(rows: Iterable[SourceRow]) -> tuple[SourceRow, ...]:
    try:
        incoming = iter(rows)
    except TypeError as error:
        raise InvalidIntake('source rows must be iterable') from error
    validated = []
    seen = set()
    for index, row in enumerate(incoming, start=1):
        if not isinstance(row, SourceRow):
            raise InvalidIntake(f'row {index} must be a SourceRow')
        if not all(is_identifier(label) for label in (row.row_id, row.section, row.crew)):
            raise InvalidIntake(f'row {index} has an invalid row, section or crew identifier')
        if row.row_id in seen:
            raise InvalidIntake(f'duplicate source row {row.row_id!r}')
        if row.amount_cents is not None and type(row.amount_cents) is not int:
            raise InvalidIntake(f'row {index} must have integer cents or a null amount')
        seen.add(row.row_id)
        validated.append(row)
    return tuple(validated)
