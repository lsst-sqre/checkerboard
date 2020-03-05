"""Tests for checkerboard, the top-level import."""

import checkerboard


def test_version() -> None:
    assert isinstance(checkerboard.__version__, str)
