"""
Unit tests for adaptive testing policy.
Verifies difficulty threshold selection, session termination, and parameter validation.
"""

import pytest

from app.modules.quiz_engine.domain.bkt.policy import (
    Difficulty,
    SessionOutcome,
    select_next_action,
)


def test_policy_enum_values():
    """Verify enum string values match API expectations."""
    assert SessionOutcome.CONTINUE == "continue"
    assert SessionOutcome.MASTERED == "mastered"
    assert Difficulty.EASY == "easy"
    assert Difficulty.MEDIUM == "medium"
    assert Difficulty.HARD == "hard"


@pytest.mark.parametrize("mastery", [0.0, 0.1, 0.25, 0.39, 0.3999])
def test_low_mastery_serves_easy_question(mastery):
    """Verify mastery < 0.4 serves EASY question to build confidence."""
    outcome, diff = select_next_action(mastery)
    assert outcome == SessionOutcome.CONTINUE
    assert diff == Difficulty.EASY


@pytest.mark.parametrize("mastery", [0.4, 0.4001, 0.55, 0.7, 0.8499])
def test_medium_mastery_serves_medium_question(mastery):
    """Verify 0.4 <= mastery < 0.85 serves MEDIUM question for maximum info gain."""
    outcome, diff = select_next_action(mastery)
    assert outcome == SessionOutcome.CONTINUE
    assert diff == Difficulty.MEDIUM


@pytest.mark.parametrize("mastery", [0.85, 0.8501, 0.92, 1.0])
def test_threshold_mastery_marks_mastered(mastery):
    """Verify mastery >= 0.85 transitions session to MASTERED with no next difficulty."""
    outcome, diff = select_next_action(mastery)
    assert outcome == SessionOutcome.MASTERED
    assert diff is None


def test_custom_mastery_threshold():
    """Verify custom mastery_threshold is respected."""
    # At mastery 0.80 with threshold 0.75 -> MASTERED
    outcome, diff = select_next_action(0.80, mastery_threshold=0.75)
    assert outcome == SessionOutcome.MASTERED
    assert diff is None

    # At mastery 0.88 with threshold 0.90 -> CONTINUE, MEDIUM
    outcome, diff = select_next_action(0.88, mastery_threshold=0.90)
    assert outcome == SessionOutcome.CONTINUE
    assert diff == Difficulty.MEDIUM


@pytest.mark.parametrize("invalid_mastery", [-0.01, -1.0, 1.01, 2.5])
def test_out_of_bounds_mastery_raises_value_error(invalid_mastery):
    """Verify mastery outside [0.0, 1.0] raises ValueError."""
    with pytest.raises(ValueError, match="Mastery must be between 0.0 and 1.0 inclusive"):
        select_next_action(invalid_mastery)


@pytest.mark.parametrize("non_numeric", ["0.5", None, [0.4], {}])
def test_non_numeric_mastery_raises_type_error(non_numeric):
    """Verify non-numeric mastery raises TypeError."""
    with pytest.raises(TypeError, match="Mastery must be a float"):
        select_next_action(non_numeric)  # type: ignore[arg-type]
