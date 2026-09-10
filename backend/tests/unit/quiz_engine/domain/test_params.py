"""
Unit tests for BKTParams dataclass and parameter validation.
"""

from dataclasses import FrozenInstanceError
import pytest

from app.modules.quiz_engine.domain.bkt.params import BKTParams, DEFAULT_PARAMS


def test_valid_bkt_params_initialization():
    """Verify BKTParams initializes correctly with valid probabilities."""
    params = BKTParams(p_l0=0.25, p_t=0.1, p_g=0.25, p_s=0.05)
    assert params.p_l0 == 0.25
    assert params.p_t == 0.1
    assert params.p_g == 0.25
    assert params.p_s == 0.05


def test_default_params_values():
    """Verify DEFAULT_PARAMS has canonical Corbett & Anderson baseline values."""
    assert DEFAULT_PARAMS.p_l0 == 0.3
    assert DEFAULT_PARAMS.p_t == 0.15
    assert DEFAULT_PARAMS.p_g == 0.2
    assert DEFAULT_PARAMS.p_s == 0.1


def test_boundary_values_zero_and_one():
    """Verify 0.0 and 1.0 are valid boundary values."""
    params_zero = BKTParams(p_l0=0.0, p_t=0.0, p_g=0.0, p_s=0.0)
    assert params_zero.p_l0 == 0.0
    params_one = BKTParams(p_l0=1.0, p_t=1.0, p_g=1.0, p_s=1.0)
    assert params_one.p_l0 == 1.0


@pytest.mark.parametrize(
    "field_name,invalid_value",
    [
        ("p_l0", -0.01),
        ("p_l0", 1.01),
        ("p_t", -0.5),
        ("p_t", 2.0),
        ("p_g", -0.0001),
        ("p_g", 1.5),
        ("p_s", -1.0),
        ("p_s", 1.001),
    ],
)
def test_out_of_bounds_parameters_raise_value_error(field_name, invalid_value):
    """Verify that values outside [0.0, 1.0] raise ValueError."""
    kwargs = {"p_l0": 0.3, "p_t": 0.15, "p_g": 0.2, "p_s": 0.1}
    kwargs[field_name] = invalid_value
    with pytest.raises(ValueError, match="must be between 0.0 and 1.0 inclusive"):
        BKTParams(**kwargs)


@pytest.mark.parametrize(
    "field_name,non_numeric_val",
    [
        ("p_l0", "invalid"),
        ("p_t", None),
        ("p_g", [0.2]),
        ("p_s", {"s": 0.1}),
    ],
)
def test_non_numeric_parameters_raise_type_error(field_name, non_numeric_val):
    """Verify that non-numeric types raise TypeError."""
    kwargs = {"p_l0": 0.3, "p_t": 0.15, "p_g": 0.2, "p_s": 0.1}
    kwargs[field_name] = non_numeric_val
    with pytest.raises(TypeError, match="must be a float"):
        BKTParams(**kwargs)


def test_bkt_params_immutability():
    """Verify that BKTParams is frozen and cannot be mutated."""
    params = BKTParams(p_l0=0.3, p_t=0.15, p_g=0.2, p_s=0.1)
    with pytest.raises(FrozenInstanceError):
        params.p_l0 = 0.5  # type: ignore[misc]
