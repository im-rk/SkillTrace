"""
Unit tests for answer normalization and correctness matching.
"""

import pytest

from app.modules.quiz_engine.domain.validation.answer_matching import (
    is_correct,
    normalize_answer,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("hello", "hello"),
        ("  hello  ", "hello"),
        ("Hello World", "hello world"),
        ("Multiple   spaces    between", "multiple spaces between"),
        ("trailing period.", "trailing period"),
        ("trailing exclamation!", "trailing exclamation"),
        ("trailing question mark?", "trailing question mark"),
        ("multiple trailing punct!??..", "multiple trailing punct"),
        ("   spaced and punct.  ", "spaced and punct"),
        ("", ""),
        (None, ""),
        (42, "42"),
        (True, "true"),
    ],
)
def test_normalize_answer(raw, expected):
    """Verify normalize_answer handles whitespace, punctuation, and casing."""
    assert normalize_answer(raw) == expected


def test_normalize_answer_case_sensitive():
    """Verify normalize_answer preserves casing when case_sensitive=True."""
    assert normalize_answer("  Hello World! ", case_sensitive=True) == "Hello World"
    assert normalize_answer("camelCase.", case_sensitive=True) == "camelCase"


@pytest.mark.parametrize(
    "sub,corr",
    [
        ("Python", "python"),
        ("  paris  ", "Paris."),
        ("42", "42"),
        ("True", "true"),
        ("  Quick   brown fox. ", "quick brown fox"),
        ("O(n log n)", "o(n log n)."),
    ],
)
def test_is_correct_matching(sub, corr):
    """Verify is_correct returns True for semantically equivalent answers."""
    assert is_correct(sub, corr) is True


@pytest.mark.parametrize(
    "sub,corr",
    [
        ("Python", "Java"),
        ("42", "43"),
        ("True", "False"),
        ("cat", "cats"),
        ("", "something"),
    ],
)
def test_is_correct_mismatch(sub, corr):
    """Verify is_correct returns False for incorrect answers."""
    assert is_correct(sub, corr) is False


def test_is_correct_case_sensitive():
    """Verify is_correct enforces exact casing when case_sensitive=True."""
    assert is_correct("Python", "python", case_sensitive=True) is False
    assert is_correct("Python", "Python", case_sensitive=True) is True
    assert is_correct("  Python. ", "Python", case_sensitive=True) is True
