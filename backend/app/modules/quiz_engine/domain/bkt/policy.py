"""
Adaptive testing policy engine.
Selects next question difficulty and session outcome based on mastery level.
"""

from enum import Enum


class SessionOutcome(str, Enum):
    CONTINUE = "continue"
    MASTERED = "mastered"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


def select_next_action(
    mastery: float,
    mastery_threshold: float = 0.85,
) -> tuple[SessionOutcome, Difficulty | None]:
    """
    Pure threshold-based policy selecting the next adaptive action.

    Decision thresholds:
      - mastery >= mastery_threshold: Student reached mastery target -> (MASTERED, None)
      - mastery < 0.4: Low mastery -> (CONTINUE, EASY)
      - 0.4 <= mastery < mastery_threshold: Moderate mastery / zone of maximum info gain -> (CONTINUE, MEDIUM)

    Args:
        mastery: Current estimated mastery probability in [0.0, 1.0].
        mastery_threshold: Target threshold to consider skill mastered (default: 0.85).

    Returns:
        tuple[SessionOutcome, Difficulty | None]
    """
    if not isinstance(mastery, (int, float)):
        raise TypeError(f"Mastery must be a float, got {type(mastery).__name__}")
    if not (0.0 <= float(mastery) <= 1.0):
        raise ValueError(f"Mastery must be between 0.0 and 1.0 inclusive, got {mastery}")

    m = float(mastery)
    if m >= mastery_threshold:
        return SessionOutcome.MASTERED, None
    if m < 0.4:
        return SessionOutcome.CONTINUE, Difficulty.EASY
    return SessionOutcome.CONTINUE, Difficulty.MEDIUM