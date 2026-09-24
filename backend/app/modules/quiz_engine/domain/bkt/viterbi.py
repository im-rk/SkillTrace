"""
Viterbi decoding for BKT: the single most likely hidden-state PATH (mastered
or not, at every step) given a whole sequence of answers -- not the same
question `update_mastery` answers.

`update_mastery` (engine.py) does exact Bayesian *filtering*: at each step it
answers "what's my best current belief, given everything so far" -- a
probability, forgotten and re-derived fresh at every step, never revised in
hindsight. Viterbi answers a different question: "looking at the WHOLE
sequence at once, what is the single most likely story of when this student
actually became mastered" -- a hard 0/1 call per step, chosen by whichever
complete path through the two states (not-mastered / mastered) has the
highest joint probability, exactly the same dynamic-programming algorithm
used for HMM part-of-speech tagging or speech recognition, here over BKT's
own two-state chain.

Standard BKT has no forgetting: mastered -> mastered with probability 1.
So the "mastered" state is absorbing, and the only real transition is
not-mastered -> mastered with probability p_t at each step.
"""
from dataclasses import dataclass

from app.modules.quiz_engine.domain.bkt.params import BKTParams


@dataclass(frozen=True)
class ViterbiStep:
    is_correct: bool
    p_t: float
    p_g: float
    p_s: float


def _emission(is_mastered: bool, is_correct: bool, p_g: float, p_s: float) -> float:
    """P(observed correctness | hidden mastery state)."""
    if is_mastered:
        return (1.0 - p_s) if is_correct else p_s
    return p_g if is_correct else (1.0 - p_g)


def most_likely_trajectory(steps: list[ViterbiStep], p_l0: float) -> list[bool]:
    """Returns one bool per step: the most likely mastery state AFTER that step,
    on the single highest-probability path through the whole sequence.

    steps: in chronological order, each carrying the BKT parameters actually
    used for that response (see ADR 0003 -- parameters are snapshotted per
    response, so a mid-sequence parameter edit doesn't change earlier steps).
    p_l0: prior mastery before the first step.
    """
    if not (0.0 <= p_l0 <= 1.0):
        raise ValueError(f"p_l0 must be between 0.0 and 1.0 inclusive, got {p_l0}")
    if not steps:
        return []

    # delta[state] = probability of the single best path ending in `state` at this step.
    # psi[state] = which PREVIOUS state that best path came from (for backtracking).
    delta = {
        True: p_l0 * _emission(True, steps[0].is_correct, steps[0].p_g, steps[0].p_s),
        False: (1.0 - p_l0) * _emission(False, steps[0].is_correct, steps[0].p_g, steps[0].p_s),
    }
    psi: list[dict[bool, bool]] = [{}]  # step 0 has no predecessor

    for prev_step, step in zip(steps, steps[1:]):
        p_t = prev_step.p_t
        # Transitions applied moving OUT of the previous step: mastered stays mastered
        # (probability 1, no forgetting); not-mastered becomes mastered with p_t, or
        # stays not-mastered with (1 - p_t). Both candidate predecessors for
        # "mastered now" are considered; only not-mastered can lead to "not mastered now".
        candidates_true = {True: delta[True] * 1.0, False: delta[False] * p_t}
        best_prev_true = max(candidates_true, key=candidates_true.get)
        new_true = candidates_true[best_prev_true] * _emission(True, step.is_correct, step.p_g, step.p_s)

        new_false = delta[False] * (1.0 - p_t) * _emission(False, step.is_correct, step.p_g, step.p_s)

        delta = {True: new_true, False: new_false}
        psi.append({True: best_prev_true, False: False})

    # Backtrack from whichever final state has the higher path probability.
    path = [max(delta, key=delta.get)]
    for step_index in range(len(steps) - 1, 0, -1):
        path.append(psi[step_index][path[-1]])
    path.reverse()
    return path
