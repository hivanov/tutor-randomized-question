import pytest
from pydantic import ValidationError as PydanticValidationError

from randomized_question_xblock.models import (
    AnswerChoice,
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
    normalize_answer_choice,
)


def test_answer_choice_model():
    choice = AnswerChoice(
        text="  Merge sort is $O(n \\log n)$  ",
        explanation="  Because recursion depth is $\\log n$ and merging takes linear time.  ",
    )
    assert choice.text == "Merge sort is $O(n \\log n)$"
    assert choice.explanation == "Because recursion depth is $\\log n$ and merging takes linear time."
    assert choice.to_dict() == {
        "text": "Merge sort is $O(n \\log n)$",
        "explanation": "Because recursion depth is $\\log n$ and merging takes linear time.",
    }

    # Empty text fails
    with pytest.raises(PydanticValidationError):
        AnswerChoice(text="   ")

    # Normalization helper
    norm_from_str = normalize_answer_choice("Simple string answer")
    assert norm_from_str.text == "Simple string answer"
    assert norm_from_str.explanation == ""

    norm_from_dict = normalize_answer_choice({"text": "Dict text", "explanation": "Dict expl"})
    assert norm_from_dict.text == "Dict text"
    assert norm_from_dict.explanation == "Dict expl"

    norm_from_model = normalize_answer_choice(choice)
    assert norm_from_model == choice


def test_option_model_serialization_and_validation():
    opt = Option(
        id="opt_1",
        text="Sample answer",
        explanation="Sample explanation why valid",
        is_correct=True,
    )
    assert opt.id == "opt_1"
    assert opt.text == "Sample answer"
    assert opt.explanation == "Sample explanation why valid"
    assert opt.is_correct is True
    assert opt.to_client_dict() == {"id": "opt_1", "text": "Sample answer"}
    assert opt.to_client_dict(reveal_details=True) == {
        "id": "opt_1",
        "text": "Sample answer",
        "explanation": "Sample explanation why valid",
        "is_correct": True,
    }

    # Blank option ID or invalid characters
    with pytest.raises(PydanticValidationError):
        Option(id="   ", text="Text", is_correct=True)

    with pytest.raises(PydanticValidationError):
        Option(id="opt@invalid!char", text="Text", is_correct=True)


def test_client_option_validation():
    opt = ClientOption(
        id="opt_valid",
        text="Option display text",
        explanation="Explanation why choice is right/wrong",
        is_correct=True,
    )
    assert opt.id == "opt_valid"
    assert opt.explanation == "Explanation why choice is right/wrong"
    assert opt.is_correct is True

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
    # Valid with strings
    pc = PoolConstraints(
        correct_pool=["C1", "C2", "C3"],
        incorrect_pool=["I1", "I2"],
        t=3,
        c=2,
    )
    assert pc.t == 3
    assert pc.c == 2

    # Valid with dicts and AnswerChoice objects
    pc_objects = PoolConstraints(
        correct_pool=[
            {"text": "C1", "explanation": "Exp C1"},
            AnswerChoice(text="C2", explanation="Exp C2"),
        ],
        incorrect_pool=[
            {"text": "I1", "explanation": "Exp I1"},
        ],
        t=2,
        c=1,
    )
    assert len(pc_objects.correct_pool) == 2
    c0 = pc_objects.correct_pool[0]
    assert isinstance(c0, AnswerChoice)
    assert c0.explanation == "Exp C1"

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
        correct_answers=[
            {"text": "C1", "explanation": "Why C1 is right"},
            {"text": "C2", "explanation": "Why C2 is right"},
        ],
        incorrect_answers=[
            {"text": "I1", "explanation": "Why I1 is wrong"},
            {"text": "I2", "explanation": "Why I2 is wrong"},
        ],
        total_options_count=3,
        correct_options_count=1,
        weight=5.0,
        show_correctness=ShowCorrectnessMode.ALWAYS,
    )
    assert payload.total_options_count == 3
    assert payload.weight == 5.0
    assert payload.show_correctness == ShowCorrectnessMode.ALWAYS
    ans0 = payload.correct_answers[0]
    assert isinstance(ans0, AnswerChoice)
    assert ans0.explanation == "Why C1 is right"

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
        options=[
            ClientOption(
                id="opt_1",
                text="Correct option",
                explanation="Explanation why correct",
                is_correct=True,
            )
        ],
    )
    dumped = submit_resp.model_dump()
    assert dumped["success"] is True
    assert dumped["score"] == 10.0
    assert dumped["is_correct"] is True
    assert dumped["attempts_remaining"] == 2
    assert dumped["options"][0]["explanation"] == "Explanation why correct"
    assert dumped["options"][0]["is_correct"] is True

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
            ClientOption(id="opt_1", text="Option 1", explanation="Why 1", is_correct=True),
            ClientOption(id="opt_2", text="Option 2", explanation="Why 2", is_correct=False),
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
    assert ctx.options[0].explanation == "Why 1"

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
        correct_answers=[
            {"text": "C1", "explanation": "Exp C1"},
            {"text": "C2", "explanation": "Exp C2"},
        ],
        incorrect_answers=[
            {"text": "I1", "explanation": "Exp I1"},
            {"text": "I2", "explanation": "Exp I2"},
        ],
        total_options_count=3,
        correct_options_count=1,
        weight=1.0,
        max_attempts=3,
        show_correctness=ShowCorrectnessMode.ALWAYS,
        explanation="Explanation",
    )
    assert ctx.total_options_count == 3
    c0 = ctx.correct_answers[0]
    assert isinstance(c0, AnswerChoice)
    assert c0.explanation == "Exp C1"

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
