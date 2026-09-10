"""
BKT domain logic engine.
Calculates forward algorithm updates.
"""

from app.modules.quiz_engine.domain.bkt.params import BKTParams


def _posterior_given_correct(prior: float, params: BKTParams) -> float:
    """
    Calculate the Bayesian posterior probability of mastery given a correct observation:
    P(L | correct) = [ P(L) * (1 - P(S)) ] / [ P(L) * (1 - P(S)) + (1 - P(L)) * P(G) ]
    """
    numerator = prior * (1.0 - params.p_s)
    denominator = numerator + (1.0 - prior) * params.p_g
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _posterior_given_incorrect(prior: float, params: BKTParams) -> float:
    """
    Calculate the Bayesian posterior probability of mastery given an incorrect observation:
    P(L | incorrect) = [ P(L) * P(S) ] / [ P(L) * P(S) + (1 - P(L)) * (1 - P(G)) ]
    """
    numerator = prior * params.p_s
    denominator = numerator + (1.0 - prior) * (1.0 - params.p_g)
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _apply_learning_transition(posterior: float, p_t: float) -> float:
    """
    Apply the Markov learning transition step:
    P(L_new) = P(L | obs) + (1 - P(L | obs)) * P(T)
    """
    return posterior + (1.0 - posterior) * p_t


def update_mastery(prior: float, is_correct: bool, params: BKTParams) -> float:
    """
    Execute the full BKT forward algorithm update.

    Args:
        prior: Prior belief of mastery in [0.0, 1.0].
        is_correct: Whether the student answered the question correctly.
        params: BKT skill parameters (p_l0, p_t, p_g, p_s).

    Returns:
        Updated mastery probability in [0.0, 1.0].
    """
    if not isinstance(prior, (int, float)):
        raise TypeError(f"Prior mastery must be a float, got {type(prior).__name__}")
    if not (0.0 <= float(prior) <= 1.0):
        raise ValueError(f"Prior mastery must be between 0.0 and 1.0 inclusive, got {prior}")

    prior_float = float(prior)
    if is_correct:
        posterior = _posterior_given_correct(prior_float, params)
    else:
        posterior = _posterior_given_incorrect(prior_float, params)

    new_mastery = _apply_learning_transition(posterior, params.p_t)
    return max(0.0, min(1.0, float(new_mastery)))