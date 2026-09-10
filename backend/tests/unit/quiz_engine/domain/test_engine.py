"""
Unit tests for BKT forward algorithm engine.
Verifies exact Bayesian inference, learning transition, edge cases, and degenerate guards.
"""

import pytest

from app.modules.quiz_engine.domain.bkt.engine import (
    _apply_learning_transition,
    _posterior_given_correct,
    _posterior_given_incorrect,
    update_mastery,
)
from app.modules.quiz_engine.domain.bkt.params import BKTParams, DEFAULT_PARAMS


def test_worked_example_correct_answer():
    """
    Verify the canonical worked example from the PRD for a correct answer:
      prior = 0.3
      DEFAULT_PARAMS: p_l0=0.3, p_t=0.15, p_g=0.2, p_s=0.1
      Bayes posterior = 0.6585
      Updated mastery = 0.710 (+-0.001)
    """
    posterior = _posterior_given_correct(0.3, DEFAULT_PARAMS)
    assert posterior == pytest.approx(0.6585, abs=1e-3)

    mastery = update_mastery(0.3, True, DEFAULT_PARAMS)
    assert mastery == pytest.approx(0.710, abs=1e-3)


def test_worked_example_incorrect_answer():
    """
    Verify the canonical worked example from the PRD for an incorrect answer:
      prior = 0.3
      DEFAULT_PARAMS: p_l0=0.3, p_t=0.15, p_g=0.2, p_s=0.1
      Bayes posterior = 0.0508
      Updated mastery = 0.193 (+-0.001)
    """
    posterior = _posterior_given_incorrect(0.3, DEFAULT_PARAMS)
    assert posterior == pytest.approx(0.0508, abs=1e-3)

    mastery = update_mastery(0.3, False, DEFAULT_PARAMS)
    assert mastery == pytest.approx(0.193, abs=1e-3)


def test_boundary_prior_zero():
    """
    When student starts at prior=0.0:
    Correct: P(L|corr) = 0.0 -> P(L_new) = 0 + (1-0)*0.15 = 0.15
    Incorrect: P(L|inc) = 0.0 -> P(L_new) = 0 + (1-0)*0.15 = 0.15
    """
    assert update_mastery(0.0, True, DEFAULT_PARAMS) == pytest.approx(0.15, abs=1e-4)
    assert update_mastery(0.0, False, DEFAULT_PARAMS) == pytest.approx(0.15, abs=1e-4)


def test_boundary_prior_one():
    """
    When student is already at prior=1.0:
    Correct: P(L|corr) = 1.0 -> P(L_new) = 1.0
    Incorrect: P(L|inc) = 1.0 (slip happened) -> P(L_new) = 1.0 (cannot unlearn)
    """
    assert update_mastery(1.0, True, DEFAULT_PARAMS) == pytest.approx(1.0, abs=1e-4)
    assert update_mastery(1.0, False, DEFAULT_PARAMS) == pytest.approx(1.0, abs=1e-4)


def test_zero_learning_rate():
    """When p_t = 0.0, update equals the Bayes posterior directly."""
    params = BKTParams(p_l0=0.3, p_t=0.0, p_g=0.2, p_s=0.1)
    expected_corr = _posterior_given_correct(0.3, params)
    assert update_mastery(0.3, True, params) == pytest.approx(expected_corr, abs=1e-6)

    expected_inc = _posterior_given_incorrect(0.3, params)
    assert update_mastery(0.3, False, params) == pytest.approx(expected_inc, abs=1e-6)


def test_max_learning_rate():
    """When p_t = 1.0, mastery jumps to 1.0 after any opportunity."""
    params = BKTParams(p_l0=0.3, p_t=1.0, p_g=0.2, p_s=0.1)
    assert update_mastery(0.3, True, params) == pytest.approx(1.0, abs=1e-6)
    assert update_mastery(0.3, False, params) == pytest.approx(1.0, abs=1e-6)


def test_degenerate_correct_denominator_zero():
    """
    Test degenerate divide-by-zero branch in _posterior_given_correct:
    When prior = 0.0 and p_g = 0.0, denominator is 0.0 -> returns 0.0.
    """
    params = BKTParams(p_l0=0.0, p_t=0.1, p_g=0.0, p_s=0.1)
    assert _posterior_given_correct(0.0, params) == 0.0
    assert update_mastery(0.0, True, params) == pytest.approx(0.1, abs=1e-4)


def test_degenerate_incorrect_denominator_zero():
    """
    Test degenerate divide-by-zero branch in _posterior_given_incorrect:
    When prior = 1.0 and p_s = 0.0, denominator is 0.0 -> returns 0.0.
    """
    params = BKTParams(p_l0=1.0, p_t=0.1, p_g=0.2, p_s=0.0)
    assert _posterior_given_incorrect(1.0, params) == 0.0
    assert update_mastery(1.0, False, params) == pytest.approx(0.1, abs=1e-4)


@pytest.mark.parametrize("invalid_prior", [-0.1, -0.0001, 1.0001, 2.0])
def test_out_of_bounds_prior_raises_value_error(invalid_prior):
    """Verify that prior outside [0.0, 1.0] raises ValueError."""
    with pytest.raises(ValueError, match="Prior mastery must be between 0.0 and 1.0 inclusive"):
        update_mastery(invalid_prior, True, DEFAULT_PARAMS)


@pytest.mark.parametrize("non_numeric_prior", ["0.5", None, [0.3], {}])
def test_non_numeric_prior_raises_type_error(non_numeric_prior):
    """Verify that non-numeric prior raises TypeError."""
    with pytest.raises(TypeError, match="Prior mastery must be a float"):
        update_mastery(non_numeric_prior, True, DEFAULT_PARAMS)  # type: ignore[arg-type]


def test_learning_transition_helper():
    """Directly test _apply_learning_transition helper function."""
    assert _apply_learning_transition(0.5, 0.2) == pytest.approx(0.6, abs=1e-6)
    assert _apply_learning_transition(0.0, 0.15) == pytest.approx(0.15, abs=1e-6)
    assert _apply_learning_transition(1.0, 0.15) == pytest.approx(1.0, abs=1e-6)


def test_consecutive_correct_answers_converge_towards_one():
    """Verify multiple correct answers monotonically increase mastery towards 1.0."""
    m = DEFAULT_PARAMS.p_l0
    for _ in range(5):
        new_m = update_mastery(m, True, DEFAULT_PARAMS)
        assert new_m > m
        m = new_m
    assert m > 0.95
