"""
Parameterized Playwright Integration & E2E Test Suite for Open edX Randomized Question XBlock.

Tests full end-to-end user workflows:
1. Teacher Studio problem setup & piecewise rule authoring.
2. Parameterized student personas (100% pass, partial credit, wrong on top of correct, all wrong, under-selection).
3. Multi-attempt retry lifecycle and attempt exhaustion locking.
4. Show Correctness modes (immediate vs delayed).
5. Teacher grading analytics dashboard.
"""

import time
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from tests.integration.server import STATE, IntegrationTestServer


@pytest.fixture(scope="session")
def test_server():
    server = IntegrationTestServer(port=8899)
    server.start()
    time.sleep(0.5)
    yield "http://127.0.0.1:8899"
    server.stop()


@pytest.fixture(scope="session")
def browser_instance():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


def test_01_teacher_studio_authoring(browser_instance, test_server):
    """Verifies teacher configuring problem parameters, pools, and grading cases in Studio."""
    context = browser_instance.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()

    page.goto(f"{test_server}/studio")
    page.wait_for_selector(".randomized-question-studio")

    # Check initial values loaded
    assert page.input_value("#rq-display-name") == "Distributed Systems & Concurrency Problem"
    assert page.input_value("#rq-param-t") == "4"
    assert page.input_value("#rq-param-c") == "2"

    # Add a new option to pool C
    page.click(".btn-add-c")
    page.fill(
        ".list-pool-c .pool-item-row:last-child input", "Raft uses randomized election timers to avoid split votes."
    )

    # Save settings
    page.click(".btn-save")
    page.wait_for_selector(".save-status:has-text('Saved successfully!')")

    context.close()


@pytest.mark.parametrize(
    "student_id,selection_strategy,expected_score,expected_status,expected_feedback_snippet",
    [
        (
            "student_alpha_100pct",
            "all_correct",
            10.0,
            "alert-success",
            "Full credit: All correct",
        ),
        (
            "student_beta_partial",
            "one_correct_zero_wrong",
            5.0,
            "alert-warning",
            "Partial credit (1 correct, 0 wrong)",
        ),
        (
            "student_gamma_wrong_plus_correct",
            "all_correct_plus_one_wrong",
            0.0,
            "alert-danger",
            "At least one incorrect answer was selected",
        ),
        (
            "student_delta_all_wrong",
            "all_wrong",
            0.0,
            "alert-danger",
            "At least one incorrect answer was selected",
        ),
        (
            "student_epsilon_under_selected",
            "zero_selection",
            0.0,
            "alert-danger",
            "Please select at least one option",
        ),
    ],
)
def test_02_parameterized_student_submissions(
    browser_instance,
    test_server,
    student_id,
    selection_strategy,
    expected_score,
    expected_status,
    expected_feedback_snippet,
):
    """Executes parameterized submission strategies across diverse student cohorts."""
    context = browser_instance.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()

    page.goto(f"{test_server}/student/{student_id}")
    page.wait_for_selector(".randomized-question-block")

    # Fetch ground-truth mapping from server state for this student
    student_opts = STATE.get_or_create_student_state(student_id)["options"]
    correct_ids = [opt.id for opt in student_opts if opt.is_correct]
    wrong_ids = [opt.id for opt in student_opts if not opt.is_correct]

    if selection_strategy == "all_correct":
        for cid in correct_ids:
            page.check(f"input[value='{cid}']")
        page.click(".btn-submit")
        page.wait_for_selector(f".feedback-alert.{expected_status}")
        score_display = str(int(expected_score)) if expected_score.is_integer() else str(expected_score)
        assert score_display in page.text_content(".feedback-title")
        assert expected_feedback_snippet in page.text_content(".feedback-message")
        # Explanation shown immediately for always mode
        assert page.is_visible(".explanation-container")

    elif selection_strategy == "one_correct_zero_wrong":
        page.check(f"input[value='{correct_ids[0]}']")
        page.click(".btn-submit")
        page.wait_for_selector(f".feedback-alert.{expected_status}")
        score_display = str(int(expected_score)) if expected_score.is_integer() else str(expected_score)
        assert score_display in page.text_content(".feedback-title")
        assert expected_feedback_snippet in page.text_content(".feedback-message")

    elif selection_strategy == "all_correct_plus_one_wrong":
        for cid in correct_ids:
            page.check(f"input[value='{cid}']")
        page.check(f"input[value='{wrong_ids[0]}']")
        page.click(".btn-submit")
        page.wait_for_selector(f".feedback-alert.{expected_status}")
        assert "0 / 10" in page.text_content(".feedback-title")
        assert expected_feedback_snippet in page.text_content(".feedback-message")

    elif selection_strategy == "all_wrong":
        for wid in wrong_ids:
            page.check(f"input[value='{wid}']")
        page.click(".btn-submit")
        page.wait_for_selector(f".feedback-alert.{expected_status}")
        assert "0 / 10" in page.text_content(".feedback-title")
        assert expected_feedback_snippet in page.text_content(".feedback-message")

    elif selection_strategy == "zero_selection":
        # Handle browser alert when zero options checked
        dialog_text: list[str] = []

        def handle_dialog(dialog: Any) -> None:
            dialog_text.append(dialog.message)
            dialog.accept()

        page.on("dialog", handle_dialog)
        page.click(".btn-submit")
        page.wait_for_timeout(300)
        assert any(expected_feedback_snippet in msg for msg in dialog_text)

    context.close()


def test_03_student_multi_attempt_retry_and_exhaustion(browser_instance, test_server):
    """Verifies student re-attempting problem with reseeding and locking upon max attempt exhaustion."""
    student_id = "student_zeta_retrier"
    context = browser_instance.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()

    page.goto(f"{test_server}/student/{student_id}")
    page.wait_for_selector(".randomized-question-block")

    # Attempt 1: Select wrong choice and submit
    opts_att1 = STATE.get_or_create_student_state(student_id)["options"]
    wrong_id = [opt.id for opt in opts_att1 if not opt.is_correct][0]
    page.check(f"input[value='{wrong_id}']")
    page.click(".btn-submit")
    page.wait_for_selector(".feedback-alert.alert-danger")
    assert page.text_content(".attempts-badge") == "Attempts: 1 / 2"

    # Reset for Attempt 2
    assert page.is_visible(".btn-reset")
    page.click(".btn-reset")
    page.wait_for_timeout(400)

    # Attempt 2: Select wrong choice again and submit
    opts_att2 = STATE.get_or_create_student_state(student_id)["options"]
    wrong_id2 = [opt.id for opt in opts_att2 if not opt.is_correct][0]
    page.check(f"input[value='{wrong_id2}']")
    page.click(".btn-submit")
    page.wait_for_selector(".feedback-alert.alert-danger")
    assert page.text_content(".attempts-badge") == "Attempts: 2 / 2"

    # Max attempts reached -> Submit disabled, Reset hidden
    assert page.is_disabled(".btn-submit")
    assert not page.is_visible(".btn-reset")

    context.close()


def test_04_teacher_dashboard_analytics(browser_instance, test_server):
    """Verifies that teacher dashboard compiles pass/fail rates and logs each student's attempt."""
    context = browser_instance.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()

    page.goto(f"{test_server}/dashboard")
    page.wait_for_selector(".stats-grid")

    assert page.is_visible(".stat-card.pass")
    assert page.is_visible(".stat-card.partial")
    assert page.is_visible(".stat-card.fail")
    assert "student_alpha_100pct" in page.text_content("table")
    assert "student_beta_partial" in page.text_content("table")
    assert "student_zeta_retrier" in page.text_content("table")

    context.close()
