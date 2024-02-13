"""Utility functions for Checkerboard."""


def stringify_item(inp: bytes | str | None) -> str:
    """Turn bytes (assumed to be utf-8) or None into str."""
    if isinstance(inp, str):
        return inp
    elif isinstance(inp, bytes):
        return inp.decode()
    elif inp is None:
        return ""
    else:
        # Ruff and mypy disagree over whether this should exist.
        return f"{inp!r}"  # type:ignore[unreachable]


def stringify_list(inp: list[bytes | str | None]) -> list[str]:
    """Turn possibly-mixed-type list[bytes|str|None] into list[str]."""
    return [stringify_item(item) for item in inp]
