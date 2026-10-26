"""
Open edX Randomized Question XBlock

Provides advanced single- and multi-select randomized problem authoring:
1. Dynamic pool sampling from Correct (C) and Incorrect (I) option sets.
2. Parameterized subset controls: total answers to appear (t) and correct answers (c).
3. Deterministic position shuffling per student attempt.
4. User-friendly custom grading function g(x) with piecewise case definitions,
   configurable strict fail defaults, and live Studio validation.
5. Standard Open edX grading controls (weight, max_attempts, show_correctness).
6. Uses Pydantic models for robust data interchange, validation, and JSON schemas.
"""

import importlib.resources
import logging
import os
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from xblock.core import XBlock
from xblock.fields import Boolean, Float, Integer, Scope, String
from xblock.fields import List as XBlockList

try:
    from web_fragments.fragment import Fragment
except ImportError:
    from xblock.fragment import Fragment  # type: ignore[no-redef]

from .engine import CaseGradingEvaluator, PoolSampler, ValidationError
from .models import (
    AnswerChoice,
    ClientOption,
    GradingCase,
    Option,
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

log = logging.getLogger(__name__)


def resource_string(path: str) -> str:
    """Helper to load a static resource file as a unicode string."""
    try:
        parts = path.split("/")
        package = "randomized_question_xblock"
        if len(parts) > 1:
            rel_path = "/".join(parts)
            ref = importlib.resources.files(package).joinpath(rel_path)
            return ref.read_text(encoding="utf-8")
        else:
            return importlib.resources.files(package).joinpath(path).read_text(encoding="utf-8")
    except Exception as e:
        log.warning(f"Failed to load resource {path} via importlib: {e}")
        base_dir = os.path.dirname(__file__)
        full_path = os.path.join(base_dir, path)
        with open(full_path, encoding="utf-8") as f:
            return f.read()


class RandomizedQuestionXBlock(XBlock):
    """
    XBlock implementing randomized answer sampling from C and I pools with case-based grading.
    """

    has_score = True

    # -------------------------------------------------------------
    # Studio Authoring Settings (Scope.settings)
    # -------------------------------------------------------------
    display_name = String(
        display_name="Display Name",
        default="Randomized Multi-Choice Question",
        scope=Scope.settings,
    )

    prompt = String(
        display_name="Question Prompt",
        default="Select all correct statements below:",
        scope=Scope.settings,
    )

    correct_answers = XBlockList(
        display_name="Correct Answers Pool (C)",
        default=[
            {
                "text": "Python supports multiple inheritance.",
                "explanation": "Python supports multiple inheritance via C3 linearization (Method Resolution Order).",
            },
            {
                "text": "List comprehensions are faster than equivalent for-loops in standard CPython.",
                "explanation": "List comprehensions execute at C speed using the LIST_APPEND opcode without repeated Python function call overhead.",
            },
            {
                "text": "Tuples are immutable sequence types.",
                "explanation": "Once created, elements and length of a tuple cannot be changed.",
            },
        ],
        scope=Scope.settings,
    )

    incorrect_answers = XBlockList(
        display_name="Incorrect Answers Pool (I)",
        default=[
            {
                "text": "Dictionaries in Python retain no insertion order.",
                "explanation": "Dictionaries in Python have preserved insertion order since Python 3.7.",
            },
            {
                "text": "A Python list is implemented as a doubly-linked list in memory.",
                "explanation": "Python lists are variable-length array pointers (dynamic arrays), not linked lists.",
            },
            {
                "text": "Strings in Python are mutable byte arrays.",
                "explanation": "Strings (str) in Python are immutable unicode sequences; bytearray is mutable.",
            },
            {
                "text": "Python does not support closures or first-class functions.",
                "explanation": "Functions in Python are first-class objects and closures are fully supported.",
            },
        ],
        scope=Scope.settings,
    )

    total_options_count = Integer(
        display_name="Total Answers to Display (t)",
        default=4,
        values={"min": 2},
        scope=Scope.settings,
    )

    correct_options_count = Integer(
        display_name="Correct Answers to Display (c)",
        default=2,
        values={"min": 1},
        scope=Scope.settings,
    )

    fail_on_any_wrong = Boolean(
        display_name="Fail (g(x)=0) if any wrong answer selected",
        default=True,
        scope=Scope.settings,
    )

    fail_if_not_all_correct = Boolean(
        display_name="Fail (g(x)=0) if not all correct answers selected",
        default=True,
        scope=Scope.settings,
    )

    grading_default_score = Float(
        display_name="Default Fallback Score Fraction (0.0 to 1.0)",
        default=0.0,
        scope=Scope.settings,
    )

    grading_cases = XBlockList(
        display_name="Custom Piecewise Grading Cases",
        default=[
            {
                "id": "case_all_correct",
                "description": "All correct and zero wrong",
                "condition_type": "all_correct",
                "condition_value": None,
                "max_wrong_allowed": 0,
                "score_fraction": 1.0,
                "feedback": "Perfect! All correct answers identified without mistakes.",
            },
            {
                "id": "case_partial_one_missed",
                "description": "Partial credit (all but one correct, zero wrong)",
                "condition_type": "min_correct",
                "condition_value": 1,
                "max_wrong_allowed": 0,
                "score_fraction": 0.5,
                "feedback": "Partial credit: Good effort, but some correct answers were missed.",
            },
        ],
        scope=Scope.settings,
    )

    weight = Float(
        display_name="Problem Weight / Points",
        default=1.0,
        values={"min": 0.0},
        scope=Scope.settings,
    )

    max_attempts = Integer(
        display_name="Maximum Attempts",
        default=3,
        values={"min": 1},
        scope=Scope.settings,
    )

    show_correctness = String(
        display_name="Show Correctness",
        default=ShowCorrectnessMode.ALWAYS.value,
        values=[mode.value for mode in ShowCorrectnessMode],
        scope=Scope.settings,
    )

    explanation = String(
        display_name="Explanation / Post-Submission Feedback",
        default="Python lists are dynamic arrays, strings and tuples are immutable, and Python guarantees dict insertion order since 3.7.",
        scope=Scope.settings,
    )

    # -------------------------------------------------------------
    # Student Runtime State (Scope.user_state)
    # -------------------------------------------------------------
    sampled_options = XBlockList(
        default=[],
        scope=Scope.user_state,
    )

    selected_ids = XBlockList(
        default=[],
        scope=Scope.user_state,
    )

    attempts = Integer(
        default=0,
        scope=Scope.user_state,
    )

    score = Float(
        default=0.0,
        scope=Scope.user_state,
    )

    completed = Boolean(
        default=False,
        scope=Scope.user_state,
    )

    last_feedback = String(
        default="",
        scope=Scope.user_state,
    )

    attempt_seed = String(
        default="",
        scope=Scope.user_state,
    )

    # -------------------------------------------------------------
    # Views & Handlers
    # -------------------------------------------------------------
    def _get_user_seed(self) -> str:
        """Generates a stable deterministic seed for the current user and attempt."""
        user_id = getattr(self.scope_ids, "user_id", "anonymous_student")
        usage_id = str(getattr(self.scope_ids, "usage_id", "usage_id"))
        return f"{user_id}:{usage_id}:attempt_{self.attempts}"

    def _ensure_sampled_options(self) -> list[Option]:
        """Ensures options are sampled and stored in student user_state as Option models."""
        valid_texts = {
            (opt.get("text", "") if isinstance(opt, dict) else str(opt)).strip()
            for opt in list(self.correct_answers) + list(self.incorrect_answers)
        }

        # Invalidate if empty or if sampled options belong to an outdated/stale pool
        is_stale = False
        if self.sampled_options:
            for opt in self.sampled_options:
                opt_text = (opt.get("text", "") if isinstance(opt, dict) else str(opt)).strip()
                if opt_text not in valid_texts:
                    is_stale = True
                    break

        if not self.sampled_options or is_stale:
            seed = self._get_user_seed()
            self.attempt_seed = seed
            options = PoolSampler.sample_and_shuffle(
                correct_pool=list(self.correct_answers),
                incorrect_pool=list(self.incorrect_answers),
                t=self.total_options_count,
                c=self.correct_options_count,
                seed=seed,
            )
            self.sampled_options = [opt.model_dump() for opt in options]
            return options

        return [Option.model_validate(opt) for opt in self.sampled_options]

    def student_view(self, context: Any = None) -> Fragment:
        """
        Renders the student-facing LMS view using StudentViewContext Pydantic model.
        """
        options = self._ensure_sampled_options()
        mode = ShowCorrectnessMode(self.show_correctness)
        reveal = self.completed and mode == ShowCorrectnessMode.ALWAYS
        selected_set = set(list(self.selected_ids))
        client_options = [
            ClientOption(
                id=opt.id,
                text=opt.text,
                explanation=opt.explanation if (reveal and opt.id in selected_set) else "",
                is_correct=opt.is_correct if reveal else None,
            )
            for opt in options
        ]

        context_model = StudentViewContext(
            display_name=self.display_name,
            prompt=self.prompt,
            options=client_options,
            selected_ids=list(self.selected_ids),
            attempts=self.attempts,
            max_attempts=self.max_attempts,
            attempts_remaining=max(0, self.max_attempts - self.attempts),
            weight=self.weight,
            score=self.score * self.weight,
            raw_score_fraction=self.score,
            completed=self.completed,
            last_feedback=self.last_feedback,
            show_correctness=mode,
            explanation=self.explanation if reveal else "",
            is_single_choice=(self.correct_options_count == 1 and self.total_options_count == 2),
        )

        html = resource_string("static/html/student_view.html")
        frag = Fragment(html)
        frag.add_css(resource_string("static/css/randomized_question.css"))
        frag.add_javascript(resource_string("static/js/randomized_question.js"))
        frag.initialize_js("RandomizedQuestionStudentView", context_model.model_dump())
        return frag

    def studio_view(self, context: Any = None) -> Fragment:
        """
        Renders the Studio authoring view using StudioViewContext Pydantic model.
        """
        parsed_cases = [GradingCase.model_validate(c) for c in self.grading_cases]
        mode = ShowCorrectnessMode(self.show_correctness)
        parsed_correct = [normalize_answer_choice(c) for c in self.correct_answers]
        parsed_incorrect = [normalize_answer_choice(i) for i in self.incorrect_answers]

        context_model = StudioViewContext(
            display_name=self.display_name,
            prompt=self.prompt,
            correct_answers=parsed_correct,
            incorrect_answers=parsed_incorrect,
            total_options_count=self.total_options_count,
            correct_options_count=self.correct_options_count,
            fail_on_any_wrong=self.fail_on_any_wrong,
            fail_if_not_all_correct=self.fail_if_not_all_correct,
            grading_default_score=self.grading_default_score,
            grading_cases=parsed_cases,
            weight=self.weight,
            max_attempts=self.max_attempts,
            show_correctness=mode,
            explanation=self.explanation,
        )

        html = resource_string("static/html/studio_view.html")
        frag = Fragment(html)
        frag.add_css(resource_string("static/css/randomized_question_studio.css"))
        frag.add_javascript(resource_string("static/js/randomized_question_studio.js"))
        frag.initialize_js("RandomizedQuestionStudioView", context_model.model_dump())
        return frag

    @XBlock.json_handler
    def studio_submit(self, data: dict[str, Any], suffix: str = "") -> dict[str, Any]:
        """
        Handles Studio settings save using StudioSettingsPayload Pydantic model.
        """
        try:
            payload = StudioSettingsPayload.model_validate(data)

            self.display_name = payload.display_name
            self.prompt = payload.prompt
            self.correct_answers = [
                item.to_dict() if isinstance(item, AnswerChoice) else normalize_answer_choice(item).to_dict()
                for item in payload.correct_answers
            ]
            self.incorrect_answers = [
                item.to_dict() if isinstance(item, AnswerChoice) else normalize_answer_choice(item).to_dict()
                for item in payload.incorrect_answers
            ]
            self.total_options_count = payload.total_options_count
            self.correct_options_count = payload.correct_options_count
            self.fail_on_any_wrong = payload.fail_on_any_wrong
            self.fail_if_not_all_correct = payload.fail_if_not_all_correct
            self.grading_default_score = payload.grading_default_score
            self.grading_cases = [case.model_dump() for case in payload.grading_cases]
            self.weight = payload.weight
            self.max_attempts = payload.max_attempts
            self.show_correctness = payload.show_correctness.value
            self.explanation = payload.explanation

            return StudioSubmitResponse(success=True).model_dump()

        except PydanticValidationError as pve:
            err_msg = "; ".join([err["msg"] for err in pve.errors()])
            return StudioSubmitResponse(success=False, error=err_msg).model_dump()
        except ValidationError as ve:
            return StudioSubmitResponse(success=False, error=str(ve)).model_dump()
        except Exception as e:
            log.exception("Error saving RandomizedQuestionXBlock studio settings")
            return StudioSubmitResponse(success=False, error=f"Failed to save settings: {e!s}").model_dump()

    @XBlock.json_handler
    def submit_answer(self, data: dict[str, Any], suffix: str = "") -> dict[str, Any]:
        """
        Handles student submission using StudentSubmissionPayload and StudentSubmitResponse Pydantic models.
        """
        if self.attempts >= self.max_attempts:
            return StudentSubmitResponse(
                success=False,
                error="Maximum attempts reached for this problem.",
                attempts=self.attempts,
                max_attempts=self.max_attempts,
                attempts_remaining=0,
            ).model_dump()

        if self.completed and self.score >= 1.0:
            return StudentSubmitResponse(
                success=False,
                error="Problem already completed with full credit.",
                attempts=self.attempts,
                max_attempts=self.max_attempts,
                attempts_remaining=max(0, self.max_attempts - self.attempts),
            ).model_dump()

        if self.completed:
            return StudentSubmitResponse(
                success=False,
                error="This attempt has already been submitted. Please click 'Try New Attempt' to start a new attempt.",
                attempts=self.attempts,
                max_attempts=self.max_attempts,
                attempts_remaining=max(0, self.max_attempts - self.attempts),
            ).model_dump()

        try:
            payload = StudentSubmissionPayload.model_validate(data)
            selected_ids_set = set(payload.selected_ids)
            self.selected_ids = list(payload.selected_ids)

            options = self._ensure_sampled_options()
            parsed_cases = [GradingCase.model_validate(c) for c in self.grading_cases]

            eval_result = CaseGradingEvaluator.evaluate(
                selected_ids=selected_ids_set,
                displayed_options=options,
                grading_cases=parsed_cases,
                fail_on_any_wrong=self.fail_on_any_wrong,
                fail_if_not_all_correct=self.fail_if_not_all_correct,
                default_score=self.grading_default_score,
            )

            self.attempts += 1
            self.score = eval_result.score
            self.completed = True
            self.last_feedback = eval_result.feedback

            if hasattr(self.runtime, "publish"):
                try:
                    self.runtime.publish(
                        self,
                        "grade",
                        {
                            "value": self.score * self.weight,
                            "max_value": self.weight,
                        },
                    )
                except Exception as e:
                    log.warning(f"Could not publish grade event to LMS runtime: {e}")

            reveal = self.show_correctness == ShowCorrectnessMode.ALWAYS.value
            revealed_options = [
                ClientOption(
                    id=opt.id,
                    text=opt.text,
                    explanation=opt.explanation if (reveal and opt.id in selected_ids_set) else "",
                    is_correct=opt.is_correct if reveal else None,
                )
                for opt in options
            ]

            resp = StudentSubmitResponse(
                success=True,
                score=self.score * self.weight,
                raw_score_fraction=self.score,
                max_score=self.weight,
                is_correct=eval_result.is_correct,
                feedback=eval_result.feedback,
                matched_case=eval_result.matched_case,
                correctly_selected=eval_result.correctly_selected,
                wrong_selected=eval_result.wrong_selected,
                attempts=self.attempts,
                max_attempts=self.max_attempts,
                attempts_remaining=max(0, self.max_attempts - self.attempts),
                explanation=self.explanation if reveal else "",
                options=revealed_options,
            )
            return resp.model_dump()

        except Exception as e:
            log.exception("Error evaluating student submission")
            return StudentSubmitResponse(
                success=False,
                error=f"Error processing submission: {e!s}",
                attempts=self.attempts,
                max_attempts=self.max_attempts,
            ).model_dump()

    @XBlock.json_handler
    def reset_problem(self, data: dict[str, Any], suffix: str = "") -> dict[str, Any]:
        """
        Resets student state and reseeds options using ResetResponse Pydantic model.
        """
        if self.attempts >= self.max_attempts:
            return ResetResponse(
                success=False,
                error="Cannot reset: maximum attempts reached.",
                attempts=self.attempts,
                max_attempts=self.max_attempts,
            ).model_dump()

        self.selected_ids = []
        seed = self._get_user_seed()
        self.attempt_seed = seed
        new_options = PoolSampler.sample_and_shuffle(
            correct_pool=list(self.correct_answers),
            incorrect_pool=list(self.incorrect_answers),
            t=self.total_options_count,
            c=self.correct_options_count,
            seed=seed,
        )
        self.sampled_options = [opt.model_dump() for opt in new_options]
        self.completed = False
        self.last_feedback = ""

        client_options = [ClientOption(id=opt.id, text=opt.text) for opt in new_options]

        resp = ResetResponse(
            success=True,
            options=client_options,
            attempts=self.attempts,
            max_attempts=self.max_attempts,
        )
        return resp.model_dump()

    # -------------------------------------------------------------
    # OLX Serialization & Deserialization
    # -------------------------------------------------------------
    @classmethod
    def parse_xml(cls, node: Any, runtime: Any, keys: Any, id_generator: Any = None) -> "RandomizedQuestionXBlock":
        """Parse XML when importing OLX courses."""
        block: RandomizedQuestionXBlock = runtime.construct_xblock_from_class(cls, keys)

        for name, value in list(node.items()):
            if name in block.fields:
                cls._set_field_if_present(block, name, value, {})

        # Parse child elements
        for child in node:
            tag = child.tag.lower()
            if tag == "prompt" and child.text and child.text.strip():
                block.prompt = child.text.strip()
            elif tag == "explanation" and child.text and child.text.strip():
                block.explanation = child.text.strip()
            elif tag == "correct_answers":
                correct_items = []
                for item in child:
                    if item.tag.lower() == "item":
                        text_elem = item.find("text")
                        expl_elem = item.find("explanation")
                        if text_elem is not None:
                            text_val = (text_elem.text or "").strip()
                            expl_val = (expl_elem.text if expl_elem is not None else "").strip()
                        elif "text" in item.attrib:
                            text_val = item.attrib.get("text", "").strip()
                            expl_val = item.attrib.get("explanation", "").strip()
                        else:
                            text_val = (item.text or "").strip()
                            expl_val = item.attrib.get("explanation", "").strip()
                        if text_val:
                            correct_items.append({"text": text_val, "explanation": expl_val})
                if correct_items:
                    block.correct_answers = correct_items
            elif tag == "incorrect_answers":
                incorrect_items = []
                for item in child:
                    if item.tag.lower() == "item":
                        text_elem = item.find("text")
                        expl_elem = item.find("explanation")
                        if text_elem is not None:
                            text_val = (text_elem.text or "").strip()
                            expl_val = (expl_elem.text if expl_elem is not None else "").strip()
                        elif "text" in item.attrib:
                            text_val = item.attrib.get("text", "").strip()
                            expl_val = item.attrib.get("explanation", "").strip()
                        else:
                            text_val = (item.text or "").strip()
                            expl_val = item.attrib.get("explanation", "").strip()
                        if text_val:
                            incorrect_items.append({"text": text_val, "explanation": expl_val})
                if incorrect_items:
                    block.incorrect_answers = incorrect_items
            elif tag == "grading_cases":
                cases = []
                for item in child:
                    if item.tag.lower() == "item":
                        cid = item.attrib.get("id", f"case_{len(cases)+1}")
                        desc = item.attrib.get("description", "")
                        ctype = item.attrib.get("condition_type", "all_correct")
                        cval = item.attrib.get("condition_value", None)
                        if cval is not None:
                            try:
                                cval = int(cval)
                            except ValueError:
                                pass
                        max_w = int(item.attrib.get("max_wrong_allowed", 0))
                        sf = float(item.attrib.get("score_fraction", 1.0))
                        fb = item.attrib.get("feedback", "")
                        cases.append({
                            "id": cid,
                            "description": desc,
                            "condition_type": ctype,
                            "condition_value": cval,
                            "max_wrong_allowed": max_w,
                            "score_fraction": sf,
                            "feedback": fb,
                        })
                if cases:
                    block.grading_cases = cases

        return block

    def add_xml_to_node(self, node: Any) -> None:
        """Export XBlock settings to OLX XML node."""
        import xml.etree.ElementTree as ET

        node.tag = "randomized_question"
        node.set("display_name", self.display_name or "Randomized Question")
        node.set("prompt", self.prompt or "")
        node.set("total_options_count", str(self.total_options_count))
        node.set("correct_options_count", str(self.correct_options_count))
        node.set("fail_on_any_wrong", "true" if self.fail_on_any_wrong else "false")
        node.set("fail_if_not_all_correct", "true" if self.fail_if_not_all_correct else "false")
        node.set("grading_default_score", str(self.grading_default_score))
        node.set("weight", str(self.weight))
        node.set("max_attempts", str(self.max_attempts))
        node.set("show_correctness", self.show_correctness or "always")
        node.set("explanation", self.explanation or "")

        # Correct answers
        correct_elem = ET.SubElement(node, "correct_answers")
        ca_list = getattr(self, "correct_answers", []) or []
        for ca in ca_list:  # type: ignore[union-attr]
            item_elem = ET.SubElement(correct_elem, "item")
            if isinstance(ca, dict):
                item_elem.text = ca.get("text", "")
                if ca.get("explanation"):
                    item_elem.set("explanation", ca["explanation"])
            elif isinstance(ca, AnswerChoice):
                item_elem.text = ca.text
                if ca.explanation:
                    item_elem.set("explanation", ca.explanation)
            else:
                item_elem.text = str(ca)

        # Incorrect answers
        incorrect_elem = ET.SubElement(node, "incorrect_answers")
        ia_list = getattr(self, "incorrect_answers", []) or []
        for ia in ia_list:  # type: ignore[union-attr]
            item_elem = ET.SubElement(incorrect_elem, "item")
            if isinstance(ia, dict):
                item_elem.text = ia.get("text", "")
                if ia.get("explanation"):
                    item_elem.set("explanation", ia["explanation"])
            elif isinstance(ia, AnswerChoice):
                item_elem.text = ia.text
                if ia.explanation:
                    item_elem.set("explanation", ia.explanation)
            else:
                item_elem.text = str(ia)

        # Grading cases
        cases_elem = ET.SubElement(node, "grading_cases")
        gc_list = getattr(self, "grading_cases", []) or []
        for gc in gc_list:  # type: ignore[union-attr]
            item_elem = ET.SubElement(cases_elem, "item")
            if isinstance(gc, dict):
                item_elem.set("id", gc.get("id", "case_1"))
                item_elem.set("description", gc.get("description", ""))
                item_elem.set("condition_type", gc.get("condition_type", "all_correct"))
                if gc.get("condition_value") is not None:
                    item_elem.set("condition_value", str(gc.get("condition_value")))
                item_elem.set("max_wrong_allowed", str(gc.get("max_wrong_allowed", 0)))
                item_elem.set("score_fraction", str(gc.get("score_fraction", 1.0)))
                item_elem.set("feedback", gc.get("feedback", ""))
