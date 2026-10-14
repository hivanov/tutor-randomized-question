import pytest
from pydantic import ValidationError as PydanticValidationError

from randomized_question_xblock.models import (
    ClientOption,
    ConditionType,
    GradingCase,
    GradingEvaluationResult,
    Option,
    PoolConstraints,
    ResetResponse,
    ShowCorrectnessMode,
    StudentSubmissionPayload,
    StudentSubmitResponse,
    StudentViewContext,
    StudioSettingsPayload,
    StudioSubmitResponse,
    StudioViewContext,
)


def test_option_model_serialization_and_validation():
    opt = Option(id="opt_1", text="Sample answer", is_correct=True)
    assert opt.id == "opt_1"
    assert opt.text == "Sample answer"
    assert opt.is_correct is True
    assert opt.to_client_dict() == {"id": "opt_1", "text": "Sample answer"}

    # Blank option ID or invalid characters
    with pytest.raises(PydanticValidationError):
        Option(id="   ", text="Text", is_correct=True)

    with pytest.raises(PydanticValidationError):
        Option(id="opt@invalid!char", text="Text", is_correct=True)


def test_client_option_validation():
    opt = ClientOption(id="opt_valid", text="Option display text")
    assert opt.id == "opt_valid"

    # Empty text fails
    with pytest.raises(PydanticValidationError):
        ClientOption(id="opt_1", text="   ")


def test_grading_case_validations():
    # Valid case with Enum
    case = GradingCase(
        id="case_1",
        description="All correct",
        condition_type=ConditionType.ALL_CORRECT,
        score_fraction=1.0,
    )
    assert case.condition_type == ConditionType.ALL_CORRECT
    assert case.score_fraction == 1.0

    # Valid string coercion to Enum
    case_str = GradingCase(
        id="case_2",
        description="Exact 2 correct",
        condition_type="exact_correct",  # type: ignore[arg-type]
        condition_value=2,
        score_fraction=0.8,
    )
    assert case_str.condition_type == ConditionType.EXACT_CORRECT

    # Invalid condition type
    with pytest.raises(PydanticValidationError):
        GradingCase(condition_type="invalid_type")  # type: ignore[arg-type]

    # Score fraction > 1.0
    with pytest.raises(PydanticValidationError):
        GradingCase(score_fraction=1.5)

    # Invalid condition_value for exact_correct (must be int >= 1)
    with pytest.raises(PydanticValidationError):
        GradingCase(
            condition_type=ConditionType.EXACT_CORRECT,
            condition_value=0,
        )

    # Invalid custom_expr characters
    with pytest.raises(PydanticValidationError):
        GradingCase(
            condition_type=ConditionType.CUSTOM_EXPR,
            condition_value="import os; os.system('ls')",
        )


def test_pool_constraints_model():
    # Valid
    pc = PoolConstraints(
        correct_pool=["C1", "C2", "C3"],
        incorrect_pool=["I1", "I2"],
        t=3,
        c=2,
    )
    assert pc.t == 3
    assert pc.c == 2

    # Invalid: c > |C|
    with pytest.raises(PydanticValidationError, match="1 <= c <= |C|"):
        PoolConstraints(
            correct_pool=["C1"],
            incorrect_pool=["I1"],
            t=2,
            c=2,
        )

    # Invalid: t > |C| + |I|
    with pytest.raises(PydanticValidationError, match="2 <= t <= |C| + |I|"):
        PoolConstraints(
            correct_pool=["C1"],
            incorrect_pool=["I1"],
            t=5,
            c=1,
        )


def test_studio_settings_payload_validation():
    payload = StudioSettingsPayload(
        display_name="Test Question",
        prompt="Select answers:",
        correct_answers=["C1", "C2"],
        incorrect_answers=["I1", "I2"],
        total_options_count=3,
        correct_options_count=1,
        weight=5.0,
        show_correctness=ShowCorrectnessMode.ALWAYS,
    )
    assert payload.total_options_count == 3
    assert payload.weight == 5.0
    assert payload.show_correctness == ShowCorrectnessMode.ALWAYS

    # String value coerced to ShowCorrectnessMode Enum
    payload_str_enum = StudioSettingsPayload(
        display_name="Test Question",
        prompt="Select answers:",
        correct_answers=["C1", "C2"],
        incorrect_answers=["I1", "I2"],
        total_options_count=3,
        correct_options_count=1,
        show_correctness="past_due",  # type: ignore[arg-type]
    )
    assert payload_str_enum.show_correctness == ShowCorrectnessMode.PAST_DUE


def test_studio_settings_duplicate_and_disjoint_pool_constraints():
    # Duplicate items in pool C
    with pytest.raises(PydanticValidationError, match="Option pool contains duplicate items"):
        StudioSettingsPayload(
            correct_answers=["Duplicate", "Duplicate"],
            incorrect_answers=["I1"],
            total_options_count=2,
            correct_options_count=1,
        )

    # Overlapping items between C and I pools
    with pytest.raises(PydanticValidationError, match="Options cannot appear in both Correct and Incorrect pools"):
        StudioSettingsPayload(
            correct_answers=["Overlap", "C2"],
            incorrect_answers=["Overlap", "I2"],
            total_options_count=3,
            correct_options_count=1,
        )


def test_grading_evaluation_result_validation():
    res = GradingEvaluationResult(
        score=1.0,
        is_correct=True,
        correctly_selected=2,
        wrong_selected=0,
        total_correct=2,
        total_wrong=2,
        matched_case="all_correct",
        feedback="Correct!",
    )
    assert res.score == 1.0

    # Inconsistent correctly_selected > total_correct
    with pytest.raises(PydanticValidationError, match="correctly_selected .* cannot exceed total_correct"):
        GradingEvaluationResult(
            score=1.0,
            is_correct=True,
            correctly_selected=5,
            wrong_selected=0,
            total_correct=2,
            total_wrong=2,
            matched_case="test",
            feedback="test",
        )


def test_student_response_models():
    submit_resp = StudentSubmitResponse(
        success=True,
        score=10.0,
        raw_score_fraction=1.0,
        max_score=10.0,
        is_correct=True,
        feedback="Great job!",
        attempts=1,
        max_attempts=3,
    )
    dumped = submit_resp.model_dump()
    assert dumped["success"] is True
    assert dumped["score"] == 10.0
    assert dumped["is_correct"] is True
    assert dumped["attempts_remaining"] == 2

    reset_resp = ResetResponse(
        success=True,
        options=[ClientOption(id="o1", text="Option 1")],
        attempts=1,
        max_attempts=3,
    )
    dumped_reset = reset_resp.model_dump()
    assert dumped_reset["options"][0]["id"] == "o1"

    sub_payload = StudentSubmissionPayload(selected_ids=["o1", "o2", "o1"])
    # Verifies deduplication in validator
    assert sub_payload.selected_ids == ["o1", "o2"]

    studio_resp = StudioSubmitResponse(success=True)
    assert studio_resp.success is True


def test_student_view_context_validation():
    ctx = StudentViewContext(
        display_name="Test Context",
        prompt="Select:",
        options=[
            ClientOption(id="opt_1", text="Option 1"),
            ClientOption(id="opt_2", text="Option 2"),
        ],
        selected_ids=["opt_1"],
        attempts=1,
        max_attempts=3,
        attempts_remaining=2,
        weight=1.0,
        score=1.0,
        raw_score_fraction=1.0,
        completed=True,
        last_feedback="Correct",
        show_correctness=ShowCorrectnessMode.ALWAYS,
        explanation="Explain",
        is_single_choice=True,
    )
    assert ctx.attempts_remaining == 2

    # Selected ID not in options
    with pytest.raises(PydanticValidationError, match="selected_ids contains IDs not in options list"):
        StudentViewContext(
            display_name="Test Context",
            prompt="Select:",
            options=[
                ClientOption(id="opt_1", text="Option 1"),
                ClientOption(id="opt_2", text="Option 2"),
            ],
            selected_ids=["opt_unknown_id"],
            attempts=1,
            max_attempts=3,
            attempts_remaining=2,
            weight=1.0,
            score=0.0,
            raw_score_fraction=0.0,
            completed=False,
            last_feedback="",
            show_correctness=ShowCorrectnessMode.ALWAYS,
            explanation="",
            is_single_choice=False,
        )


def test_studio_view_context_validation():
    ctx = StudioViewContext(
        display_name="Studio Title",
        prompt="Studio Prompt",
        correct_answers=["C1", "C2"],
        incorrect_answers=["I1", "I2"],
        total_options_count=3,
        correct_options_count=1,
        weight=1.0,
        max_attempts=3,
        show_correctness=ShowCorrectnessMode.ALWAYS,
        explanation="Explanation",
    )
    assert ctx.total_options_count == 3

    # Incompatible pool bounds in studio context
    with pytest.raises(PydanticValidationError):
        StudioViewContext(
            display_name="Studio Title",
            prompt="Studio Prompt",
            correct_answers=["C1"],
            incorrect_answers=["I1"],
            total_options_count=10,  # exceeds |C| + |I| = 2
            correct_options_count=1,
            weight=1.0,
            max_attempts=3,
            show_correctness=ShowCorrectnessMode.ALWAYS,
            explanation="",
        )
