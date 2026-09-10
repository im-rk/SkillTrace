"""
BKT domain parameters.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BKTParams:
    """
    Standard Bayesian Knowledge Tracing parameters.

    Attributes:
        p_l0: Prior probability that a student knows a skill before any practice.
        p_t:  Transition probability (learning rate) of learning a skill after a practice opportunity.
        p_g:  Guess probability: P(correct | not mastered).
        p_s:  Slip probability: P(incorrect | mastered).
    """

    p_l0: float
    p_t: float
    p_g: float
    p_s: float

    def __post_init__(self) -> None:
        """Validate that all probability parameters are within [0.0, 1.0]."""
        for param_name in ("p_l0", "p_t", "p_g", "p_s"):
            val = getattr(self, param_name)
            if not isinstance(val, (int, float)):
                raise TypeError(f"Parameter '{param_name}' must be a float, got {type(val).__name__}")
            if not (0.0 <= float(val) <= 1.0):
                raise ValueError(
                    f"Parameter '{param_name}' must be between 0.0 and 1.0 inclusive, got {val}"
                )


# Literature standard default parameters (Corbett & Anderson baseline)
DEFAULT_PARAMS = BKTParams(
    p_l0=0.3,
    p_t=0.15,
    p_g=0.2,
    p_s=0.1,
)