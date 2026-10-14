import pytest

from randomized_question_xblock.engine import CaseGradingEvaluator
from randomized_question_xblock.models import (
    ConditionType,
    GradingCase,
    GradingEvaluationResult,
    Option,
)


@pytest.fixture
def sample_displayed_options():
    return [
        Option(id="opt_c1", text="Correct 1", is_correct=True),
        Option(id="opt_c2", text="Correct 2", is_correct=True),
        Option(id="opt_i1", text="Incorrect 1", is_correct=False),
        Option(id="opt_i2", text="Incorrect 2", is_correct=False),
    ]


def test_default_grading_all_correct_no_wrong(sample_displayed_options):
    selected = {"opt_c1", "opt_c2"}
    result: GradingEvaluationResult = CaseGradingEvaluator.evaluate(
        selected_ids=selected,
        displayed_options=sample_displayed_options,
        grading_cases=None,
        fail_on_any_wrong=True,
        fail_if_not_all_correct=True,
        default_score=0.0,
    )

    assert result.score == 1.0
    assert result.is_correct is True
    assert result.correctly_selected == 2
    assert result.wrong_selected == 0
    assert result.failed_reason is None


def test_default_fail_rule_1_wrong_answer_selected(sample_displayed_options):
    selected = {"opt_c1", "opt_c2", "opt_i1"}
    result: GradingEvaluationResult = CaseGradingEvaluator.evaluate(
        selected_ids=selected,
        displayed_options=sample_displayed_options,
        grading_cases=None,
        fail_on_any_wrong=True,
        fail_if_not_all_correct=True,
        default_score=0.0,
    )

    assert result.score == 0.0
    assert result.is_correct is False
    assert result.correctly_selected == 2
    assert result.wrong_selected == 1
    assert "At least one incorrect answer was selected" in result.feedback


def test_default_fail_rule_2_not_all_correct_selected(sample_displayed_options):
    selected = {"opt_c1"}
    result: GradingEvaluationResult = CaseGradingEvaluator.evaluate(
        selected_ids=selected,
        displayed_options=sample_displayed_options,
        grading_cases=None,
        fail_on_any_wrong=True,
        fail_if_not_all_correct=True,
        default_score=0.0,
    )

    assert result.score == 0.0
    assert result.is_correct is False
    assert result.correctly_selected == 1
    assert result.wrong_selected == 0
    assert "Not all correct answers were selected" in result.feedback


def test_custom_piecewise_grading_cases(sample_displayed_options):
    cases = [
        GradingCase(
            id="case_full",
            description="100% full credit for all correct",
            condition_type=ConditionType.ALL_CORRECT,
            condition_value=None,
            max_wrong_allowed=0,
            score_fraction=1.0,
            feedback="Perfect score!",
        ),
        GradingCase(
            id="case_partial_1",
            description="50% partial credit for 1 correct and 0 wrong",
            condition_type=ConditionType.EXACT_CORRECT,
            condition_value=1,
            max_wrong_allowed=0,
            score_fraction=0.5,
            feedback="Half points awarded.",
        ),
    ]

    res_partial = CaseGradingEvaluator.evaluate(
        selected_ids={"opt_c1"},
        displayed_options=sample_displayed_options,
        grading_cases=cases,
        fail_on_any_wrong=True,
        fail_if_not_all_correct=False,
    )
    assert res_partial.score == 0.5
    assert res_partial.feedback == "Half points awarded."

    res_full = CaseGradingEvaluator.evaluate(
        selected_ids={"opt_c1", "opt_c2"},
        displayed_options=sample_displayed_options,
        grading_cases=cases,
    )
    assert res_full.score == 1.0
    assert res_full.feedback == "Perfect score!"


def test_custom_expression_case(sample_displayed_options):
    cases = [
        GradingCase(
            id="case_expr",
            description="Custom condition (x == 2 and w == 0)",
            condition_type=ConditionType.CUSTOM_EXPR,
            condition_value="x == 2 and w == 0",
            max_wrong_allowed=0,
            score_fraction=0.85,
            feedback="Matched expression rule.",
        )
    ]

    result = CaseGradingEvaluator.evaluate(
        selected_ids={"opt_c1", "opt_c2"},
        displayed_options=sample_displayed_options,
        grading_cases=cases,
    )
    assert result.score == 0.85
    assert result.feedback == "Matched expression rule."
