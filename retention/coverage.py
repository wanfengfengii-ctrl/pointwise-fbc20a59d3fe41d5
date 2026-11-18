from collections.abc import Collection, Iterable
from dataclasses import dataclass

from intake.identity import is_identifier


class InvalidCoverage(ValueError):
    pass


@dataclass(frozen=True, slots=True, order=True)
class Coverage:
    sections: tuple[str, ...]


def normalize_sections(
    sections: Iterable[str], known: Collection[str]
) -> tuple[str, ...]:
    if isinstance(sections, (str, bytes)):
        raise InvalidCoverage('supply a collection of section identifiers')
    try:
        requested = tuple(sections)
    except TypeError as error:
        raise InvalidCoverage('section collection must be iterable') from error
    if not requested:
        raise InvalidCoverage('section collection is empty')
    if not all(is_identifier(section) for section in requested):
        raise InvalidCoverage('invalid section identifier')
    unique = set(requested)
    unknown = unique.difference(known)
    if unknown:
        raise InvalidCoverage(f'unknown sections {sorted(unknown)!r}')
    return tuple(sorted(unique))


def normalize_coverages(
    scopes: Iterable[Iterable[str]], known: Collection[str]
) -> tuple[Coverage, ...]:
    if isinstance(scopes, (str, bytes)):
        raise InvalidCoverage('supply a collection of scopes')
    try:
        incoming = iter(scopes)
    except TypeError as error:
        raise InvalidCoverage('coverage collection must be iterable') from error
    coverages = {Coverage(normalize_sections(scope, known)) for scope in incoming}
    if not coverages:
        raise InvalidCoverage('at least one coverage is required')
    return tuple(sorted(coverages))
