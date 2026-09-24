"""
Unit tests for Viterbi decoding of the most likely BKT mastery-state trajectory.
"""
import pytest

from app.modules.quiz_engine.domain.bkt.params import DEFAULT_PARAMS
from app.modules.quiz_engine.domain.bkt.viterbi import ViterbiStep, most_likely_trajectory

P = DEFAULT_PARAMS  # p_l0=0.3, p_t=0.15, p_g=0.2, p_s=0.1


def steps(*correctness: bool, params=P) -> list[ViterbiStep]:
    return [ViterbiStep(is_correct=c, p_t=params.p_t, p_g=params.p_g, p_s=params.p_s) for c in correctness]


def test_empty_sequence_returns_empty_path():
    assert most_likely_trajectory([], P.p_l0) == []


def test_all_correct_eventually_settles_on_mastered():
    path = most_likely_trajectory(steps(True, True, True, True, True, True), P.p_l0)
    assert len(path) == 6
    assert path[-1] is True
    # mastery is absorbing: once the path says True, it never says False again
    first_true = path.index(True)
    assert all(path[first_true:])


def test_all_incorrect_never_reaches_mastered():
    path = most_likely_trajectory(steps(False, False, False, False), P.p_l0)
    assert path == [False, False, False, False]


def test_single_correct_answer_with_high_prior_is_mastered():
    """A student who already looks mastered (prior 0.9) staying correct once should
    decode as mastered -- the emission overwhelmingly favors it."""
    path = most_likely_trajectory(steps(True), 0.9)
    assert path == [True]


def test_single_wrong_answer_with_low_prior_is_not_mastered():
    path = most_likely_trajectory(steps(False), 0.05)
    assert path == [False]


def test_once_mastered_state_is_absorbing_regardless_of_later_wrong_answers():
    """No forgetting in this model: a later wrong answer is explained as a slip
    (P(S)), not as un-mastering -- the discrete path must never flip back to False
    after it has said True."""
    path = most_likely_trajectory(steps(True, True, True, True, False, False, False), P.p_l0)
    true_positions = [i for i, v in enumerate(path) if v]
    if true_positions:
        assert all(path[true_positions[0]:])


def test_trajectory_length_always_matches_input_length():
    for n in range(1, 8):
        assert len(most_likely_trajectory(steps(*([True, False] * n)[:n]), P.p_l0)) == n


def test_per_step_parameters_are_respected_not_just_the_first_steps():
    """Regression guard against the obvious implementation bug: reusing steps[0]'s
    p_t/p_g/p_s for every step instead of each step's own. Compares the real function
    against exactly that buggy variant and requires them to diverge on a case built to
    expose it (step 2's guess rate flips from "uninformative" to "near-certain")."""

    def buggy_trajectory(steps_: list[ViterbiStep], p_l0: float) -> list[bool]:
        first = steps_[0]
        return most_likely_trajectory([ViterbiStep(s.is_correct, first.p_t, first.p_g, first.p_s) for s in steps_], p_l0)

    from app.modules.quiz_engine.domain.bkt.params import BKTParams

    sequence = [
        ViterbiStep(False, P.p_t, P.p_g, P.p_s),  # step 1: a wrong answer, ordinary params
        ViterbiStep(True, 0.5, 0.01, 0.01),  # step 2: a correct answer, near-diagnostic of mastery
    ]

    real = most_likely_trajectory(sequence, 0.3)
    buggy = buggy_trajectory(sequence, 0.3)  # would wrongly grade step 2's correct answer using step 1's params
    assert real != buggy
    assert real[-1] is True  # near-diagnostic params correctly infer mastery from the one correct answer
    assert buggy[-1] is False  # the bug would miss it -- both wrong-answer params, unconvinced


def test_rejects_out_of_range_prior():
    with pytest.raises(ValueError):
        most_likely_trajectory(steps(True), 1.5)
