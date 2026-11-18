from dataclasses import dataclass
from datetime import date


def is_identifier(value: object) -> bool:
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        return False
    try:
        value.encode('utf-8')
    except UnicodeError:
        return False
    return True


def business_date(value: date | str) -> date:
    if type(value) is date:
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError('business date must be YYYY-MM-DD') from error
        if parsed.isoformat() == value:
            return parsed
    raise ValueError('business date must be a date or YYYY-MM-DD')


@dataclass(frozen=True, slots=True, order=True)
class RevisionKey:
    batch_day: date
    revision: str

    def __post_init__(self) -> None:
        if type(self.batch_day) is not date or not is_identifier(self.revision):
            raise ValueError('invalid revision identity')

    @classmethod
    def from_parts(cls, batch_day: date | str, revision: str) -> 'RevisionKey':
        return cls(business_date(batch_day), revision)

    def sql_key(self) -> tuple[str, str]:
        return self.batch_day.isoformat(), self.revision
