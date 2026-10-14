"""
Core engine for Randomized Multi-Choice Problem Sampling and Case-Based Grading.

Uses Pydantic models for validated data interchange and strongly-typed evaluation.
"""

import hashlib
import random
import re
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from .models import (
    GradingCase,
    GradingEvaluationResult,
    Option,
    PoolConstraints,
)


class ValidationError(Exception):
    """Raised when question parameters or pool constraints are invalid."""


class PoolSampler:
    """
    Handles validation, sampling, and shuffling of choices from C and I pools.
    """

    @staticmethod
    def validate_constraints(correct_pool: list[str], incorrect_pool: list[str], t: int, c: int) -> PoolConstraints:
        """
        Validates mathematical constraints via Pydantic model:
        - len(C) >= 1
        - len(I) >= 0
        - 1 <= c <= len(C)
        - 2 <= t <= len(C) + len(I)
        - (t - c) >= 0 and (t - c) <= len(I)
        """
        try:
            return PoolConstraints(
                correct_pool=correct_pool,
                incorrect_pool=incorrect_pool,
                t=t,
                c=c,
            )
        except (PydanticValidationError, ValueError) as e:
            if isinstance(e, PydanticValidationError):
                err_msg = "; ".join([err["msg"] for err in e.errors()])
            else:
                err_msg = str(e)
            raise ValidationError(err_msg) from e

    @staticmethod
    def sample_and_shuffle(
        correct_pool: list[str],
        incorrect_pool: list[str],
        t: int,
        c: int,
        seed: str | None = None,
    ) -> list[Option]:
        """
        Deterministically samples c correct and (t - c) incorrect items,
        returning a list of validated Option Pydantic models with randomized positions.
        """
        PoolSampler.validate_constraints(correct_pool, incorrect_pool, t, c)

        rng = random.Random()
        if seed is not None:
            seed_int = int(hashlib.sha256(str(seed).encode()).hexdigest()[:16], 16)
            rng.seed(seed_int)

        sampled_c = rng.sample(correct_pool, c)
        needed_i = t - c
        sampled_i = rng.sample(incorrect_pool, needed_i) if needed_i > 0 else []

        options: list[Option] = []
        for text in sampled_c:
            opt_id = hashlib.md5(f"c:{text}".encode()).hexdigest()[:8]
            options.append(Option(id=f"opt_{opt_id}", text=text, is_correct=True))

        for text in sampled_i:
            opt_id = hashlib.md5(f"i:{text}".encode()).hexdigest()[:8]
            options.append(Option(id=f"opt_{opt_id}", text=text, is_correct=False))

        rng.shuffle(options)
        return options


class CaseGradingEvaluator:
    """
    Evaluates student response against a custom piecewise grading function g(x).
    """

    @staticmethod
    def evaluate(
        selected_ids: set[str],
        displayed_options: Sequence[Option | dict[str, Any]],
        grading_cases: Sequence[GradingCase | dict[str, Any]] | None = None,
        fail_on_any_wrong: bool = True,
        fail_if_not_all_correct: bool = True,
        default_score: float = 0.0,
    ) -> GradingEvaluationResult:
        """
        Evaluates the selection and returns a validated GradingEvaluationResult Pydantic model.
        """
        normalized_options: list[Option] = []
        for opt in displayed_options:
            if isinstance(opt, Option):
                normalized_options.append(opt)
            elif isinstance(opt, dict):
                normalized_options.append(Option.model_validate(opt))

        normalized_cases: list[GradingCase] = []
        if grading_cases:
            for case in grading_cases:
                if isinstance(case, GradingCase):
                    normalized_cases.append(case)
                elif isinstance(case, dict):
                    normalized_cases.append(GradingCase.model_validate(case))

        correct_ids = {opt.id for opt in normalized_options if opt.is_correct}
        wrong_ids = {opt.id for opt in normalized_options if not opt.is_correct}

        total_correct = len(correct_ids)
        total_wrong = len(wrong_ids)

        chosen_correct = selected_ids & correct_ids
        chosen_wrong = selected_ids & wrong_ids

        x = len(chosen_correct)  # number of correctly guessed answers
        w = len(chosen_wrong)  # number of wrong answers selected

        failed_reason = None
        if fail_on_any_wrong and w > 0:
            failed_reason = f"At least one incorrect answer was selected ({w} wrong)."
        elif fail_if_not_all_correct and x < total_correct:
            failed_reason = f"Not all correct answers were selected ({x} of {total_correct} chosen)."

        # If strict failure triggered and no explicit custom cases defined
        if failed_reason is not None and not normalized_cases:
            return GradingEvaluationResult(
                score=0.0,
                is_correct=False,
                correctly_selected=x,
                wrong_selected=w,
                total_correct=total_correct,
                total_wrong=total_wrong,
                matched_case="default_fail",
                feedback=failed_reason,
                failed_reason=failed_reason,
            )

        # Evaluate piecewise custom cases in priority order
        if normalized_cases:
            for case in normalized_cases:
                if CaseGradingEvaluator._matches_case(case, x, w, total_correct, total_wrong):
                    score = max(0.0, min(1.0, float(case.score_fraction)))
                    return GradingEvaluationResult(
                        score=score,
                        is_correct=score >= 1.0,
                        correctly_selected=x,
                        wrong_selected=w,
                        total_correct=total_correct,
                        total_wrong=total_wrong,
                        matched_case=case.description or case.id,
                        feedback=case.feedback,
                        failed_reason=failed_reason,
                    )

        # If no custom case matched, apply standard fail logic
        if failed_reason is not None:
            return GradingEvaluationResult(
                score=0.0,
                is_correct=False,
                correctly_selected=x,
                wrong_selected=w,
                total_correct=total_correct,
                total_wrong=total_wrong,
                matched_case="default_fail",
                feedback=failed_reason,
                failed_reason=failed_reason,
            )

        # Standard full credit when all correct and zero wrong
        if x == total_correct and w == 0:
            return GradingEvaluationResult(
                score=1.0,
                is_correct=True,
                correctly_selected=x,
                wrong_selected=w,
                total_correct=total_correct,
                total_wrong=total_wrong,
                matched_case="all_correct",
                feedback="Correct! Excellent job.",
                failed_reason=None,
            )

        fallback_clamped = max(0.0, min(1.0, float(default_score)))
        return GradingEvaluationResult(
            score=fallback_clamped,
            is_correct=fallback_clamped >= 1.0,
            correctly_selected=x,
            wrong_selected=w,
            total_correct=total_correct,
            total_wrong=total_wrong,
            matched_case="default_fallback",
            feedback="Incorrect selection.",
            failed_reason=failed_reason,
        )

    @staticmethod
    def _matches_case(case: GradingCase, x: int, w: int, total_c: int, total_w: int) -> bool:
        cond_type = case.condition_type
        cond_val = case.condition_value
        max_wrong_allowed = int(case.max_wrong_allowed)

        if w > max_wrong_allowed:
            return False

        if cond_type == "all_correct":
            return x == total_c and w <= max_wrong_allowed
        elif cond_type == "exact_correct":
            target = int(cond_val) if cond_val is not None else total_c
            return x == target and w <= max_wrong_allowed
        elif cond_type == "min_correct":
            target = int(cond_val) if cond_val is not None else 1
            return x >= target and w <= max_wrong_allowed
        elif cond_type == "custom_expr":
            return CaseGradingEvaluator._eval_safe_expr(str(cond_val), x, w, total_c, total_w)
        return False

    @staticmethod
    def _eval_safe_expr(expr: str, x: int, w: int, c: int, total_w: int) -> bool:
        clean = expr.strip()
        if not re.match(r"^[0-9xwc\s\+\-\*\/\=\!\<\>\&\|\(\)andornot]+$", clean):
            return False

        safe_env = {
            "x": x,
            "w": w,
            "c": c,
            "total_c": c,
            "total_w": total_w,
        }
        try:
            clean_py = re.sub(r"(?<![=!<>])=(?![=])", "==", clean)
            return bool(eval(clean_py, {"__builtins__": {}}, safe_env))  # noqa: S307
        except Exception:
            return False
