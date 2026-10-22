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


def test_sample_and_shuffle_preserves_explanations():
    correct_pool = [
        {"text": "C1", "explanation": "Why C1 is right"},
        {"text": "C2", "explanation": "Why C2 is right"},
    ]
    incorrect_pool = [
        {"text": "I1", "explanation": "Why I1 is wrong"},
        {"text": "I2", "explanation": "Why I2 is wrong"},
    ]

    options = PoolSampler.sample_and_shuffle(correct_pool, incorrect_pool, t=3, c=2, seed="seed_expl_test")
    assert len(options) == 3
    for opt in options:
        if opt.text == "C1":
            assert opt.explanation == "Why C1 is right"
            assert opt.is_correct is True
        elif opt.text == "C2":
            assert opt.explanation == "Why C2 is right"
            assert opt.is_correct is True
        elif opt.text == "I1":
            assert opt.explanation == "Why I1 is wrong"
            assert opt.is_correct is False
        elif opt.text == "I2":
            assert opt.explanation == "Why I2 is wrong"
            assert opt.is_correct is False


def test_sample_and_shuffle_random_subsets_and_positions():
    """Verifies that across different render attempts/seeds, both subsets and option order vary."""
    c_pool = [f"Correct Fact {i}" for i in range(20)]
    i_pool = [f"Incorrect Distractor {i}" for i in range(20)]

    drawn_subsets: set[frozenset[str]] = set()
    correct_positions_distribution: list[list[int]] = []

    for attempt in range(15):
        opts = PoolSampler.sample_and_shuffle(
            correct_pool=c_pool,
            incorrect_pool=i_pool,
            t=5,
            c=2,
            seed=f"student_x:attempt_{attempt}",
        )
        assert len(opts) == 5
        assert sum(1 for o in opts if o.is_correct) == 2

        # Record subset of choices
        subset = frozenset(o.text for o in opts)
        drawn_subsets.add(subset)

        # Record index positions of the correct choices
        positions = [idx for idx, o in enumerate(opts) if o.is_correct]
        correct_positions_distribution.append(positions)

    # Across 15 attempts, we should see multiple different random subsets chosen
    assert len(drawn_subsets) > 5

    # Across 15 attempts, the positions of correct items must not be fixed at static indices
    unique_position_combos = {tuple(pos) for pos in correct_positions_distribution}
    assert len(unique_position_combos) > 3

