def encode_cents(amount: int) -> str:
    # Hexadecimal TEXT preserves Python integers beyond SQLite's INTEGER range.
    return format(amount, 'x')


def decode_cents(encoded: str) -> int:
    return int(encoded, 16)
