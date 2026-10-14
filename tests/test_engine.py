import pytest

from randomized_question_xblock.engine import PoolSampler, ValidationError
from randomized_question_xblock.models import Option


def test_validate_constraints_valid():
    correct_pool = ["C1", "C2", "C3"]
    incorrect_pool = ["I1", "I2", "I3", "I4"]

    # Valid: t=4, c=2, |C|=3, |I|=4 -> t-c=2 <= |I|
    constraints = PoolSampler.validate_constraints(correct_pool, incorrect_pool, t=4, c=2)
    assert constraints.t == 4
    assert constraints.c == 2

    # Valid: all correct shown (c=3, t=5, needed_i=2)
    PoolSampler.validate_constraints(correct_pool, incorrect_pool, t=5, c=3)

    # Valid: minimal bounds t=2, c=1
    PoolSampler.validate_constraints(correct_pool, incorrect_pool, t=2, c=1)


def test_validate_constraints_empty_c_fails():
    with pytest.raises(ValidationError, match="at least 1 item"):
        PoolSampler.validate_constraints([], ["I1", "I2"], t=2, c=1)


def test_validate_constraints_insufficient_total_options():
    with pytest.raises(ValidationError, match="Total available answers .* must be at least 2"):
        PoolSampler.validate_constraints(["C1"], [], t=2, c=1)


def test_validate_constraints_c_out_of_bounds():
    correct_pool = ["C1", "C2"]
    incorrect_pool = ["I1", "I2"]

    # c > |C|
    with pytest.raises(ValidationError, match="1 <= c <= |C|"):
        PoolSampler.validate_constraints(correct_pool, incorrect_pool, t=3, c=3)

    # c < 1
    with pytest.raises(ValidationError):
        PoolSampler.validate_constraints(correct_pool, incorrect_pool, t=2, c=0)


def test_validate_constraints_t_out_of_bounds():
    correct_pool = ["C1", "C2"]
    incorrect_pool = ["I1", "I2"]

    # t > |C| + |I|
    with pytest.raises(ValidationError, match="2 <= t <= |C| + |I|"):
        PoolSampler.validate_constraints(correct_pool, incorrect_pool, t=5, c=2)

    # t < 2
    with pytest.raises(ValidationError):
        PoolSampler.validate_constraints(correct_pool, incorrect_pool, t=1, c=1)


def test_validate_constraints_t_smaller_than_c():
    correct_pool = ["C1", "C2", "C3"]
    incorrect_pool = ["I1", "I2"]

    with pytest.raises(ValidationError, match="Total answers count .* cannot be less than correct answers count"):
        PoolSampler.validate_constraints(correct_pool, incorrect_pool, t=2, c=3)


def test_validate_constraints_insufficient_incorrect_pool():
    correct_pool = ["C1", "C2", "C3", "C4"]
    incorrect_pool = ["I1"]  # Only 1 incorrect available

    # t=3, c=1 -> needs 2 incorrect, but only 1 exists
    with pytest.raises(ValidationError, match="Incorrect answers required .* exceeds available incorrect pool"):
        PoolSampler.validate_constraints(correct_pool, incorrect_pool, t=3, c=1)


def test_sample_and_shuffle_deterministic_seed():
    correct_pool = ["C1", "C2", "C3", "C4"]
    incorrect_pool = ["I1", "I2", "I3", "I4", "I5"]

    run1 = PoolSampler.sample_and_shuffle(correct_pool, incorrect_pool, t=4, c=2, seed="student_123:attempt_1")
    run2 = PoolSampler.sample_and_shuffle(correct_pool, incorrect_pool, t=4, c=2, seed="student_123:attempt_1")

    assert len(run1) == 4
    assert len(run2) == 4
    assert all(isinstance(opt, Option) for opt in run1)

    # Identical seed must produce exactly identical order and item choices
    assert [opt.id for opt in run1] == [opt.id for opt in run2]
    assert [opt.text for opt in run1] == [opt.text for opt in run2]

    # Verify correct vs incorrect breakdown
    correct_count = sum(1 for opt in run1 if opt.is_correct)
    incorrect_count = sum(1 for opt in run1 if not opt.is_correct)
    assert correct_count == 2
    assert incorrect_count == 2


def test_sample_and_shuffle_different_seeds_vary():
    correct_pool = [f"Correct {i}" for i in range(10)]
    incorrect_pool = [f"Wrong {i}" for i in range(10)]

    run_a = PoolSampler.sample_and_shuffle(correct_pool, incorrect_pool, t=5, c=2, seed="user_a")
    run_b = PoolSampler.sample_and_shuffle(correct_pool, incorrect_pool, t=5, c=2, seed="user_b")

    texts_a = [opt.text for opt in run_a]
    texts_b = [opt.text for opt in run_b]

    # Different seeds should produce different draws/permutations
    assert texts_a != texts_b
