"""
Pydantic models for data interchange, validation, and serialization in RandomizedQuestionXBlock.
"""

import re
from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ShowCorrectnessMode(StrEnum):
    """Enumeration controlling when correctness indicators and feedback are revealed to learners."""

    ALWAYS = "always"
    PAST_DUE = "past_due"
    NEVER = "never"


class ConditionType(StrEnum):
    """Enumeration of supported evaluation conditions for piecewise grading cases."""

    ALL_CORRECT = "all_correct"
    EXACT_CORRECT = "exact_correct"
    MIN_CORRECT = "min_correct"
    CUSTOM_EXPR = "custom_expr"


class AnswerChoice(BaseModel):
    """Authoring model for an individual option in an answer pool, with optional explanation."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "text": "Python supports multiple inheritance.",
                    "explanation": "Python uses C3 linearization (Method Resolution Order) to support multiple inheritance.",
                }
            ]
        },
    )

    text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Display text of the answer choice (Markdown, LaTeX math, and code supported).",
        examples=["Python supports multiple inheritance."],
    )
    explanation: str = Field(
        default="",
        max_length=10000,
        description="Optional explanation why this answer choice is valid or invalid.",
        examples=["Python uses C3 linearization (Method Resolution Order) to support multiple inheritance."],
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Answer choice text cannot be empty or whitespace.")
        return clean

    @field_validator("explanation")
    @classmethod
    def clean_explanation(cls, v: str) -> str:
        return v.strip() if v else ""

    def to_dict(self) -> dict[str, str]:
        return {"text": self.text, "explanation": self.explanation}


def normalize_answer_choice(item: Any) -> AnswerChoice:
    """Helper to normalize a string, dict, or AnswerChoice into an AnswerChoice model."""
    if isinstance(item, AnswerChoice):
        return item
    if isinstance(item, str):
        clean = item.strip()
        if not clean:
            raise ValueError("Answer choice string cannot be blank.")
        return AnswerChoice(text=clean, explanation="")
    if isinstance(item, dict):
        text = str(item.get("text", "")).strip()
        expl = str(item.get("explanation", "")).strip()
        if not text:
            raise ValueError("Answer choice dict must contain a non-empty 'text' field.")
        return AnswerChoice(text=text, explanation=expl)
    raise ValueError(f"Unsupported answer choice format: {type(item)}")


class Option(BaseModel):
    """Internal model for a sampled option item including its ground-truth answer key and explanation."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "opt_a1b2c3d4",
                    "text": "Python supports multiple inheritance.",
                    "explanation": "Python supports multiple inheritance via C3 MRO.",
                    "is_correct": True,
                }
            ]
        },
    )

    id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique deterministic identifier for the option within the attempt.",
        examples=["opt_a1b2c3d4"],
    )
    text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Display text of the answer choice.",
        examples=["Python supports multiple inheritance."],
    )
    explanation: str = Field(
        default="",
        max_length=10000,
        description="Optional explanation of why this option is valid or invalid.",
        examples=["Python supports multiple inheritance via C3 MRO."],
    )
    is_correct: bool = Field(
        default=True,
        description="Ground-truth flag indicating whether this choice is correct.",
        examples=[True],
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Option id cannot be blank.")
        if not re.match(r"^[a-zA-Z0-9_\-:]+$", clean):
            raise ValueError("Option id must contain only alphanumeric characters, underscores, colons, or dashes.")
        return clean

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Option text cannot be empty or whitespace.")
        return clean

    @field_validator("explanation")
    @classmethod
    def clean_explanation(cls, v: str) -> str:
        return v.strip() if v else ""

    def to_client_dict(self, reveal_details: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "text": self.text}
        if reveal_details:
            result["explanation"] = self.explanation
            result["is_correct"] = self.is_correct
        return result


class ClientOption(BaseModel):
    """Sanitized option model exposed to student client UI."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "opt_a1b2c3d4",
                    "text": "Python supports multiple inheritance.",
                    "explanation": "Python supports multiple inheritance via C3 MRO.",
                    "is_correct": True,
                }
            ]
        },
    )

    id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique identifier of the choice for submission.",
        examples=["opt_a1b2c3d4"],
    )
    text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Display text of the answer option.",
        examples=["Python supports multiple inheritance."],
    )
    explanation: str = Field(
        default="",
        max_length=10000,
        description="Optional explanation why this choice is valid or invalid (revealed post-submission).",
        examples=["Python supports multiple inheritance via C3 MRO."],
    )
    is_correct: bool | None = Field(
        default=None,
        description="Whether this choice was correct (revealed post-submission when correctness is enabled).",
        examples=[True, False, None],
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("ClientOption id cannot be blank.")
        return clean

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("ClientOption text cannot be empty or whitespace.")
        return clean

    @field_validator("explanation")
    @classmethod
    def clean_explanation(cls, v: str) -> str:
        return v.strip() if v else ""


class GradingCase(BaseModel):
    """Piecewise grading case model defining an outcome rule for g(x)."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "id": "case_full_credit",
                    "description": "Full credit: All correct with zero wrong choices",
                    "condition_type": ConditionType.ALL_CORRECT,
                    "condition_value": None,
                    "max_wrong_allowed": 0,
                    "score_fraction": 1.0,
                    "feedback": "Perfect! All correct answers were selected.",
                }
            ]
        },
    )

    id: str = Field(
        default_factory=lambda: "case_default",
        min_length=1,
        max_length=64,
        description="Unique identifier for this grading case rule.",
        examples=["case_full_credit", "case_partial_credit"],
    )
    description: str = Field(
        default="Grading Case",
        min_length=1,
        max_length=255,
        description="Human-readable description of this case for instructors.",
        examples=[
            "Full credit: All correct with zero wrong choices",
            "Partial credit (1 correct, 0 wrong)",
        ],
    )
    condition_type: ConditionType = Field(
        default=ConditionType.ALL_CORRECT,
        description="The condition category evaluated against the student selection.",
        examples=[ConditionType.ALL_CORRECT, ConditionType.EXACT_CORRECT],
    )
    condition_value: int | str | None = Field(
        default=None,
        description="Target parameter value for exact_correct, min_correct, or custom_expr rules.",
        examples=[2, 1, "x == 2 and w == 0"],
    )
    max_wrong_allowed: int = Field(
        default=0,
        ge=0,
        le=50,
        description="Maximum count of wrong options allowed before this case fails to match.",
        examples=[0, 1],
    )
    score_fraction: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Fraction of problem weight awarded when this case matches (0.0 to 1.0).",
        examples=[1.0, 0.5, 0.25],
    )
    feedback: str = Field(
        default="Graded via custom case rule.",
        max_length=1000,
        description="Custom message shown to the student upon matching this case.",
        examples=[
            "Perfect! All correct answers were selected.",
            "Partial credit: You correctly identified 1 answer.",
        ],
    )

    @field_validator("id", "description", "feedback")
    @classmethod
    def clean_strings(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Field cannot be empty or solely whitespace.")
        return clean

    @model_validator(mode="after")
    def validate_condition_value(self) -> "GradingCase":
        if self.condition_type in (ConditionType.EXACT_CORRECT, ConditionType.MIN_CORRECT):
            if self.condition_value is not None:
                try:
                    int_val = int(self.condition_value)
                    if int_val < 1:
                        raise ValueError(f"condition_value for {self.condition_type} must be an integer >= 1.")
                except (ValueError, TypeError) as e:
                    raise ValueError(f"condition_value for {self.condition_type} must be an integer.") from e
        elif self.condition_type == ConditionType.CUSTOM_EXPR:
            if not self.condition_value or not str(self.condition_value).strip():
                raise ValueError("condition_value must be provided for custom_expr condition type.")
            expr = str(self.condition_value).strip()
            if not re.match(r"^[0-9xwc\s\+\-\*\/\=\!\<\>\&\|\(\)andornot]+$", expr):
                raise ValueError(
                    f"Invalid characters in custom expression: '{expr}'. Allowed: x, w, c, numbers, operators."
                )
        return self


class PoolConstraints(BaseModel):
    """Validation model enforcing mathematical bounds between pools C, I and counts t, c."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "correct_pool": [
                        {"text": "Ans A", "explanation": "Why A is correct"},
                        {"text": "Ans B", "explanation": "Why B is correct"},
                        {"text": "Ans C", "explanation": "Why C is correct"},
                    ],
                    "incorrect_pool": [
                        {"text": "Wrong 1", "explanation": "Why 1 is wrong"},
                        {"text": "Wrong 2", "explanation": "Why 2 is wrong"},
                        {"text": "Wrong 3", "explanation": "Why 3 is wrong"},
                    ],
                    "t": 4,
                    "c": 2,
                }
            ]
        },
    )

    correct_pool: Sequence[AnswerChoice | str | dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Set of ground-truth correct answer items (Pool C).",
    )
    incorrect_pool: Sequence[AnswerChoice | str | dict[str, Any]] = Field(
        default_factory=list,
        max_length=100,
        description="Set of ground-truth incorrect answer items (Pool I).",
    )
    t: int = Field(
        ...,
        ge=2,
        le=100,
        description="Total count of answer options to display to the learner.",
        examples=[4, 5],
    )
    c: int = Field(
        ...,
        ge=1,
        le=100,
        description="Count of correct answer options to display in each draw.",
        examples=[2, 1],
    )

    @field_validator("correct_pool", "incorrect_pool", mode="before")
    @classmethod
    def coerce_and_clean_pool_items(cls, items: Any) -> list[AnswerChoice]:
        if not isinstance(items, list):
            raise ValueError("Pool items must be provided as a list.")
        cleaned: list[AnswerChoice] = []
        seen_texts: set[str] = set()
        for raw in items:
            choice = normalize_answer_choice(raw)
            if choice.text in seen_texts:
                raise ValueError(f"Option pool contains duplicate items; '{choice.text}' is duplicated.")
            seen_texts.add(choice.text)
            cleaned.append(choice)
        return cleaned

    @model_validator(mode="after")
    def validate_pool_bounds(self) -> "PoolConstraints":
        c_len = len(self.correct_pool)
        i_len = len(self.incorrect_pool)
        total_available = c_len + i_len

        # Disjoint check by answer text
        c_texts = {
            item.text
            if isinstance(item, AnswerChoice)
            else (item if isinstance(item, str) else str(item.get("text", "")))
            for item in self.correct_pool
        }
        i_texts = {
            item.text
            if isinstance(item, AnswerChoice)
            else (item if isinstance(item, str) else str(item.get("text", "")))
            for item in self.incorrect_pool
        }
        overlap = c_texts & i_texts
        if overlap:
            raise ValueError(f"Options cannot appear in both Correct and Incorrect pools: {overlap}")

        if c_len < 1:
            raise ValueError("Correct answers pool (C) must contain at least 1 item.")

        if total_available < 2:
            raise ValueError(f"Total available answers (|C| + |I| = {total_available}) must be at least 2.")

        if not (1 <= self.c <= c_len):
            raise ValueError(f"Correct answers count (c={self.c}) must satisfy 1 <= c <= |C| (where |C|={c_len}).")

        if not (2 <= self.t <= total_available):
            raise ValueError(
                f"Total answers count (t={self.t}) must satisfy 2 <= t <= |C| + |I| (where |C| + |I|={total_available})."
            )

        needed_incorrect = self.t - self.c
        if needed_incorrect < 0:
            raise ValueError(
                f"Total answers count (t={self.t}) cannot be less than correct answers count (c={self.c})."
            )

        if needed_incorrect > i_len:
            raise ValueError(
                f"Incorrect answers required (t - c = {needed_incorrect}) exceeds available incorrect pool |I|={i_len}."
            )

        return self


class StudioSettingsPayload(BaseModel):
    """Payload sent by Open edX Studio authoring view when saving question configuration."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "display_name": "Python Sequence Types",
                    "prompt": "Select all immutable built-in sequences in Python:",
                    "correct_answers": [
                        {"text": "tuple", "explanation": "Tuples cannot be modified in place."},
                        {"text": "str", "explanation": "Strings are immutable sequences of unicode characters."},
                        {"text": "bytes", "explanation": "Bytes sequence is immutable."},
                        {"text": "frozenset", "explanation": "Frozenset is an immutable set."},
                    ],
                    "incorrect_answers": [
                        {"text": "list", "explanation": "Lists are mutable sequences."},
                        {"text": "bytearray", "explanation": "bytearray is a mutable sequence of bytes."},
                        {"text": "dict", "explanation": "Dictionaries are mutable mapping objects."},
                        {"text": "set", "explanation": "Sets are mutable collections."},
                    ],
                    "total_options_count": 4,
                    "correct_options_count": 2,
                    "fail_on_any_wrong": True,
                    "fail_if_not_all_correct": True,
                    "grading_default_score": 0.0,
                    "weight": 2.0,
                    "max_attempts": 3,
                    "show_correctness": ShowCorrectnessMode.ALWAYS,
                    "explanation": "Tuples, strings, and bytes are immutable; lists and bytearrays are mutable.",
                }
            ]
        },
    )

    display_name: str = Field(
        default="Randomized Multi-Choice Question",
        min_length=1,
        max_length=255,
        description="Problem title displayed in the course unit header.",
        examples=["Python Sequence Types", "Randomized Multi-Choice Problem"],
    )
    prompt: str = Field(
        default="Select all correct statements below:",
        min_length=1,
        max_length=10000,
        description="The instructional problem prompt (Markdown, LaTeX math, and HTML supported).",
        examples=[
            "Select all immutable built-in sequences in Python:",
            "Which of the following statements about HTTP/3 are true?",
        ],
    )
    correct_answers: Sequence[AnswerChoice | str | dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Ground-truth correct answer choices pool (C) with optional explanations.",
    )
    incorrect_answers: Sequence[AnswerChoice | str | dict[str, Any]] = Field(
        default_factory=list,
        max_length=100,
        description="Ground-truth incorrect answer choices pool (I) with optional explanations.",
    )
    total_options_count: int = Field(
        default=4,
        ge=2,
        le=50,
        description="Total count of options to randomly sample and display (t).",
        examples=[4, 5],
    )
    correct_options_count: int = Field(
        default=2,
        ge=1,
        le=50,
        description="Number of correct options to sample in each student draw (c).",
        examples=[2, 1],
    )
    fail_on_any_wrong: bool = Field(
        default=True,
        description="Whether selecting any wrong option triggers strict zero grade (g(x)=0).",
        examples=[True, False],
    )
    fail_if_not_all_correct: bool = Field(
        default=True,
        description="Whether omitting any displayed correct option triggers strict zero grade (g(x)=0).",
        examples=[True, False],
    )
    grading_default_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fallback score fraction awarded when no explicit case matches.",
        examples=[0.0, 0.25],
    )
    grading_cases: list[GradingCase] = Field(
        default_factory=list,
        max_length=50,
        description="Ordered list of piecewise grading cases evaluated sequentially.",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1000.0,
        description="Maximum graded points for this problem in the course gradebook.",
        examples=[1.0, 10.0, 100.0],
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        le=100,
        description="Maximum allowed submission attempts per student.",
        examples=[3, 1, 5],
    )
    show_correctness: ShowCorrectnessMode = Field(
        default=ShowCorrectnessMode.ALWAYS,
        description="Controls when green/red correctness indicators and explanations are shown.",
        examples=[ShowCorrectnessMode.ALWAYS, ShowCorrectnessMode.PAST_DUE],
    )
    explanation: str = Field(
        default="",
        max_length=10000,
        description="Post-submission solution explanation or pedagogical feedback.",
        examples=["Tuples, strings, and bytes are immutable; lists and bytearrays are mutable."],
    )

    @field_validator("display_name", "prompt")
    @classmethod
    def clean_text_fields(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Field cannot be empty or whitespace.")
        return clean

    @field_validator("correct_answers", "incorrect_answers", mode="before")
    @classmethod
    def coerce_pool_items(cls, items: Any) -> list[AnswerChoice]:
        if not isinstance(items, list):
            raise ValueError("Pool must be a list.")
        cleaned: list[AnswerChoice] = []
        seen_texts: set[str] = set()
        for raw in items:
            choice = normalize_answer_choice(raw)
            if choice.text in seen_texts:
                raise ValueError("Option pool contains duplicate items; all options in a pool must be unique.")
            seen_texts.add(choice.text)
            cleaned.append(choice)
        return cleaned

    @model_validator(mode="after")
    def validate_all_constraints(self) -> "StudioSettingsPayload":
        PoolConstraints(
            correct_pool=self.correct_answers,
            incorrect_pool=self.incorrect_answers,
            t=self.total_options_count,
            c=self.correct_options_count,
        )

        case_ids = [case.id for case in self.grading_cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Grading case IDs must be unique across all defined cases.")

        return self


class StudentSubmissionPayload(BaseModel):
    """Payload sent by the student LMS frontend upon submitting selected answers."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={"examples": [{"selected_ids": ["opt_a1b2c3d4", "opt_e5f6g7h8"]}]},
    )

    selected_ids: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="List of choice IDs selected by the learner.",
        examples=[["opt_a1b2c3d4", "opt_e5f6g7h8"]],
    )

    @field_validator("selected_ids")
    @classmethod
    def clean_selected_ids(cls, ids: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for raw_id in ids:
            clean = raw_id.strip()
            if clean and clean not in seen:
                seen.add(clean)
                cleaned.append(clean)
        return cleaned


class GradingEvaluationResult(BaseModel):
    """Internal result model returned by the CaseGradingEvaluator engine."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "score": 1.0,
                    "is_correct": True,
                    "correctly_selected": 2,
                    "wrong_selected": 0,
                    "total_correct": 2,
                    "total_wrong": 2,
                    "matched_case": "all_correct",
                    "feedback": "Correct! Excellent job.",
                    "failed_reason": None,
                }
            ]
        },
    )

    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Computed score fraction in the range [0.0, 1.0].",
        examples=[1.0, 0.5, 0.0],
    )
    is_correct: bool = Field(
        description="Flag indicating if the submission achieved full credit.",
        examples=[True, False],
    )
    correctly_selected: int = Field(
        ge=0,
        description="Count of correctly selected answers among displayed options (x).",
        examples=[2, 1, 0],
    )
    wrong_selected: int = Field(
        ge=0,
        description="Count of incorrectly selected answers among displayed options (w).",
        examples=[0, 1, 2],
    )
    total_correct: int = Field(
        ge=0,
        description="Total correct options displayed in the current attempt (c).",
        examples=[2, 3],
    )
    total_wrong: int = Field(
        ge=0,
        description="Total incorrect options displayed in the current attempt.",
        examples=[2, 3],
    )
    matched_case: str = Field(
        min_length=1,
        description="Identifier or description of the matched grading rule.",
        examples=["all_correct", "case_partial_credit", "default_fail"],
    )
    feedback: str = Field(
        description="Evaluator feedback string returned to the learner.",
        examples=[
            "Correct! Excellent job.",
            "Partial credit: You correctly identified 1 answer.",
            "At least one incorrect answer was selected (1 wrong).",
        ],
    )
    failed_reason: str | None = Field(
        default=None,
        description="Specific reason if a default failure rule was triggered.",
        examples=[
            None,
            "At least one incorrect answer was selected (1 wrong).",
            "Not all correct answers were selected (1 of 2 chosen).",
        ],
    )

    @model_validator(mode="after")
    def validate_eval_consistency(self) -> "GradingEvaluationResult":
        if self.correctly_selected > self.total_correct:
            raise ValueError(
                f"correctly_selected ({self.correctly_selected}) cannot exceed total_correct ({self.total_correct})."
            )
        if self.wrong_selected > self.total_wrong:
            raise ValueError(f"wrong_selected ({self.wrong_selected}) cannot exceed total_wrong ({self.total_wrong}).")
        return self


class StudentSubmitResponse(BaseModel):
    """Standardized JSON response returned to the student frontend after submission."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "score": 2.0,
                    "raw_score_fraction": 1.0,
                    "max_score": 2.0,
                    "is_correct": True,
                    "feedback": "Correct! Excellent job.",
                    "matched_case": "all_correct",
                    "correctly_selected": 2,
                    "wrong_selected": 0,
                    "attempts": 1,
                    "max_attempts": 3,
                    "attempts_remaining": 2,
                    "explanation": "Tuples are immutable.",
                    "options": [
                        {
                            "id": "opt_a1b2c3d4",
                            "text": "Python supports multiple inheritance.",
                            "explanation": "Python supports multiple inheritance via C3 MRO.",
                            "is_correct": True,
                        }
                    ],
                    "error": None,
                }
            ]
        }
    )

    success: bool = Field(
        default=True,
        description="Whether evaluation succeeded.",
        examples=[True, False],
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        description="Scaled earned score points (fraction * weight).",
        examples=[2.0, 0.0, 10.0],
    )
    raw_score_fraction: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Raw normalized score in range [0.0, 1.0].",
        examples=[1.0, 0.5, 0.0],
    )
    max_score: float = Field(
        default=1.0,
        ge=0.0,
        description="Problem weight / total points possible.",
        examples=[2.0, 10.0],
    )
    is_correct: bool = Field(
        default=False,
        description="Whether the attempt achieved full credit.",
        examples=[True, False],
    )
    feedback: str = Field(
        default="",
        description="Feedback text displayed to learner.",
        examples=["Correct! Excellent job.", "At least one incorrect answer was selected."],
    )
    matched_case: str = Field(
        default="",
        description="Description of the matched case.",
        examples=["all_correct", "case_partial_credit"],
    )
    correctly_selected: int = Field(
        default=0,
        ge=0,
        description="Count of correct choices selected (x).",
        examples=[2, 1, 0],
    )
    wrong_selected: int = Field(
        default=0,
        ge=0,
        description="Count of wrong choices selected (w).",
        examples=[0, 1],
    )
    attempts: int = Field(
        default=0,
        ge=0,
        description="Number of attempts consumed.",
        examples=[1, 2, 3],
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Maximum allowed attempts.",
        examples=[3, 5],
    )
    attempts_remaining: int = Field(
        default=0,
        ge=0,
        description="Attempts remaining.",
        examples=[2, 1, 0],
    )
    explanation: str = Field(
        default="",
        description="Overall solution explanation if visibility rules permit.",
        examples=["Tuples are immutable sequence types."],
    )
    options: list[ClientOption] = Field(
        default_factory=list,
        description="Options list with revealed explanations and correctness indicators when permitted.",
    )
    error: str | None = Field(
        default=None,
        description="Error message in case of failure.",
        examples=[None, "Maximum attempts reached for this problem."],
    )

    @model_validator(mode="after")
    def validate_attempts_remaining(self) -> "StudentSubmitResponse":
        expected_remaining = max(0, self.max_attempts - self.attempts)
        if self.attempts_remaining != expected_remaining:
            object.__setattr__(self, "attempts_remaining", expected_remaining)
        return self


class StudioSubmitResponse(BaseModel):
    """Standardized JSON response returned to Open edX Studio after settings save."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"success": True, "error": None},
                {"success": False, "error": "Pool C must contain at least 1 item."},
            ]
        }
    )

    success: bool = Field(
        default=True,
        description="Whether settings were successfully persisted.",
        examples=[True, False],
    )
    error: str | None = Field(
        default=None,
        description="Validation or operational error message.",
        examples=[None, "Total count (t=5) must satisfy 2 <= t <= |C| + |I|."],
    )

    @model_validator(mode="after")
    def validate_error_presence(self) -> "StudioSubmitResponse":
        if not self.success and not self.error:
            object.__setattr__(self, "error", "Operation failed.")
        return self


class ResetResponse(BaseModel):
    """Standardized JSON response returned when learner requests a new attempt with reseeded choices."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "options": [{"id": "opt_123", "text": "New sample option"}],
                    "attempts": 1,
                    "max_attempts": 3,
                    "error": None,
                }
            ]
        }
    )

    success: bool = Field(
        default=True,
        description="Whether re-randomization succeeded.",
        examples=[True, False],
    )
    options: list[ClientOption] = Field(
        default_factory=list,
        description="Newly sampled and shuffled choices.",
        examples=[[{"id": "opt_a1b2c3d4", "text": "Python supports multiple inheritance."}]],
    )
    attempts: int = Field(
        default=0,
        ge=0,
        description="Current attempt number.",
        examples=[1, 2],
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Maximum allowed attempts.",
        examples=[3, 5],
    )
    error: str | None = Field(
        default=None,
        description="Error message if reset was rejected.",
        examples=[None, "Cannot reset: maximum attempts reached."],
    )


class StudentViewContext(BaseModel):
    """Context model passed to render and initialize the student-facing LMS UI."""

    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Problem display name.",
        examples=["Randomized Multi-Choice Question"],
    )
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Problem prompt (supports Markdown, LaTeX formulas, and code).",
        examples=["Select all correct statements below:"],
    )
    options: list[ClientOption] = Field(
        ...,
        min_length=2,
        description="Sampled and shuffled choice options.",
        examples=[[{"id": "opt_a1b2c3d4", "text": "Python supports multiple inheritance."}]],
    )
    selected_ids: list[str] = Field(
        default_factory=list,
        description="Currently selected choice IDs.",
        examples=[["opt_a1b2c3d4"]],
    )
    attempts: int = Field(
        default=0,
        ge=0,
        description="Consumed attempts.",
        examples=[0, 1, 2],
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Maximum allowed attempts.",
        examples=[3, 5],
    )
    attempts_remaining: int = Field(
        default=3,
        ge=0,
        description="Remaining attempts.",
        examples=[3, 2, 1],
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Problem weight.",
        examples=[1.0, 10.0],
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        description="Current earned score.",
        examples=[0.0, 10.0],
    )
    raw_score_fraction: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Current score fraction [0.0, 1.0].",
        examples=[0.0, 1.0],
    )
    completed: bool = Field(
        default=False,
        description="Whether problem has been submitted.",
        examples=[False, True],
    )
    last_feedback: str = Field(
        default="",
        description="Last evaluation feedback.",
        examples=["", "Correct! Excellent job."],
    )
    show_correctness: ShowCorrectnessMode = Field(
        default=ShowCorrectnessMode.ALWAYS,
        description="Correctness mode.",
        examples=[ShowCorrectnessMode.ALWAYS],
    )
    explanation: str = Field(
        default="",
        description="Overall explanation text.",
        examples=["", "Python lists are dynamic arrays."],
    )
    is_single_choice: bool = Field(
        default=False,
        description="Whether to render as single-choice radio buttons.",
        examples=[False, True],
    )

    @field_validator("display_name", "prompt")
    @classmethod
    def clean_text_fields(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Field cannot be empty or whitespace.")
        return clean

    @field_validator("options")
    @classmethod
    def validate_unique_options(cls, opts: list[ClientOption]) -> list[ClientOption]:
        ids = [o.id for o in opts]
        if len(ids) != len(set(ids)):
            raise ValueError("StudentViewContext options must have unique IDs.")
        return opts

    @model_validator(mode="after")
    def validate_context_invariants(self) -> "StudentViewContext":
        valid_ids = {o.id for o in self.options}
        invalid_selections = set(self.selected_ids) - valid_ids
        if invalid_selections:
            raise ValueError(f"selected_ids contains IDs not in options list: {invalid_selections}")

        expected_remaining = max(0, self.max_attempts - self.attempts)
        if self.attempts_remaining != expected_remaining:
            object.__setattr__(self, "attempts_remaining", expected_remaining)

        return self


class StudioViewContext(BaseModel):
    """Context model passed to render and initialize the Studio authoring view UI."""

    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Problem display name.",
        examples=["Randomized Multi-Choice Question"],
    )
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Problem prompt (Markdown, LaTeX math, and code supported).",
        examples=["Select all correct statements below:"],
    )
    correct_answers: Sequence[AnswerChoice | str | dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Correct answers pool (C) with optional explanations.",
    )
    incorrect_answers: Sequence[AnswerChoice | str | dict[str, Any]] = Field(
        default_factory=list,
        max_length=100,
        description="Incorrect answers pool (I) with optional explanations.",
    )
    total_options_count: int = Field(
        ...,
        ge=2,
        le=50,
        description="Total answers count (t).",
        examples=[4, 5],
    )
    correct_options_count: int = Field(
        ...,
        ge=1,
        le=50,
        description="Correct answers count (c).",
        examples=[2, 3],
    )
    fail_on_any_wrong: bool = Field(
        default=True,
        description="Fail on any wrong choice.",
        examples=[True, False],
    )
    fail_if_not_all_correct: bool = Field(
        default=True,
        description="Fail if not all correct chosen.",
        examples=[True, False],
    )
    grading_default_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Default fallback score fraction.",
        examples=[0.0, 0.25],
    )
    grading_cases: list[GradingCase] = Field(
        default_factory=list,
        max_length=50,
        description="Grading cases.",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1000.0,
        description="Problem weight.",
        examples=[1.0, 10.0],
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        le=100,
        description="Maximum attempts.",
        examples=[3, 5],
    )
    show_correctness: ShowCorrectnessMode = Field(
        default=ShowCorrectnessMode.ALWAYS,
        description="Correctness mode.",
        examples=[ShowCorrectnessMode.ALWAYS],
    )
    explanation: str = Field(
        default="",
        max_length=10000,
        description="Post-submission general explanation.",
        examples=["Python lists are dynamic arrays, strings are immutable."],
    )

    @field_validator("display_name", "prompt")
    @classmethod
    def clean_text_fields(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Field cannot be empty or whitespace.")
        return clean

    @field_validator("correct_answers", "incorrect_answers", mode="before")
    @classmethod
    def coerce_pool_items(cls, items: Any) -> list[AnswerChoice]:
        if not isinstance(items, list):
            raise ValueError("Pool must be a list.")
        cleaned: list[AnswerChoice] = []
        seen_texts: set[str] = set()
        for raw in items:
            choice = normalize_answer_choice(raw)
            if choice.text in seen_texts:
                raise ValueError("Option pool contains duplicate items; all options in a pool must be unique.")
            seen_texts.add(choice.text)
            cleaned.append(choice)
        return cleaned

    @model_validator(mode="after")
    def validate_all_constraints(self) -> "StudioViewContext":
        PoolConstraints(
            correct_pool=self.correct_answers,
            incorrect_pool=self.incorrect_answers,
            t=self.total_options_count,
            c=self.correct_options_count,
        )

        case_ids = [case.id for case in self.grading_cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Grading case IDs must be unique across all defined cases.")

        return self
