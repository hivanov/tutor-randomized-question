import json

import webob
from xblock.field_data import DictFieldData
from xblock.fields import ScopeIds
from xblock.test.tools import TestRuntime

from randomized_question_xblock.xblock import RandomizedQuestionXBlock


def create_xblock():
    field_data = DictFieldData({})
    scope_ids = ScopeIds(
        user_id="test_student_42",
        block_type="randomized_question",
        def_id="def_id",
        usage_id="block-v1:CourseX+RQ101+type@randomized_question+block@prob1",
    )
    runtime = TestRuntime(services={"field-data": field_data})
    block = runtime.construct_xblock_from_class(RandomizedQuestionXBlock, scope_ids=scope_ids)
    block.correct_answers = ["Correct A", "Correct B", "Correct C"]
    block.incorrect_answers = ["Wrong 1", "Wrong 2", "Wrong 3", "Wrong 4"]
    block.total_options_count = 4
    block.correct_options_count = 2
    block.weight = 10.0
    block.max_attempts = 2
    return block


def make_post_request(data: dict) -> webob.Request:
    req = webob.Request.blank("/")
    req.method = "POST"
    req.body = json.dumps(data).encode("utf-8")
    return req


def test_student_view_fragment():
    block = create_xblock()
    frag = block.student_view()
    assert frag is not None
    assert "randomized-question-block" in frag.content
    assert len(block.sampled_options) == 4
    correct_count = sum(1 for o in block.sampled_options if o["is_correct"])
    assert correct_count == 2


def test_studio_view_fragment():
    block = create_xblock()
    frag = block.studio_view()
    assert frag is not None
    assert "randomized-question-studio" in frag.content


def test_studio_submit_valid():
    block = create_xblock()
    payload = {
        "display_name": "Updated Question Title",
        "prompt": "Choose all that apply:",
        "correct_answers": ["C1", "C2", "C3", "C4"],
        "incorrect_answers": ["I1", "I2", "I3"],
        "total_options_count": 5,
        "correct_options_count": 3,
        "fail_on_any_wrong": True,
        "fail_if_not_all_correct": True,
        "grading_default_score": 0.0,
        "grading_cases": [
            {
                "id": "c1",
                "description": "Full score",
                "condition_type": "all_correct",
                "condition_value": None,
                "score_fraction": 1.0,
            }
        ],
        "weight": 20.0,
        "max_attempts": 3,
        "show_correctness": "always",
        "explanation": "Test explanation.",
    }

    req = make_post_request(payload)
    resp = block.studio_submit(req)
    res_data = json.loads(resp.body)

    assert res_data["success"] is True
    assert block.display_name == "Updated Question Title"
    assert block.total_options_count == 5
    assert block.correct_options_count == 3
    assert block.weight == 20.0


def test_studio_submit_invalid_constraints():
    block = create_xblock()
    # Total count t=10 exceeds |C|+|I|=5
    payload = {
        "correct_answers": ["C1", "C2"],
        "incorrect_answers": ["I1", "I2", "I3"],
        "total_options_count": 10,
        "correct_options_count": 2,
    }
    req = make_post_request(payload)
    resp = block.studio_submit(req)
    res_data = json.loads(resp.body)

    assert res_data["success"] is False
    assert "must satisfy 2 <= t <= |C| + |I|" in res_data["error"]


def test_submit_answer_full_lifecycle():
    block = create_xblock()
    block._ensure_sampled_options()
    correct_ids = [opt["id"] for opt in block.sampled_options if opt["is_correct"]]
    wrong_ids = [opt["id"] for opt in block.sampled_options if not opt["is_correct"]]

    # Attempt 1: Submit partial/wrong answer
    req1 = make_post_request({"selected_ids": [correct_ids[0], wrong_ids[0]]})
    resp1 = block.submit_answer(req1)
    res_data1 = json.loads(resp1.body)

    assert res_data1["success"] is True
    assert res_data1["is_correct"] is False
    assert res_data1["score"] == 0.0
    assert block.attempts == 1

    # Reset for attempt 2
    req_reset = make_post_request({})
    reset_resp = block.reset_problem(req_reset)
    reset_data = json.loads(reset_resp.body)
    assert reset_data["success"] is True

    # Re-fetch new sampled options after reset
    new_correct_ids = [opt["id"] for opt in block.sampled_options if opt["is_correct"]]

    # Attempt 2: Submit all correct answers
    req2 = make_post_request({"selected_ids": new_correct_ids})
    resp2 = block.submit_answer(req2)
    res_data2 = json.loads(resp2.body)

    assert res_data2["success"] is True
    assert res_data2["is_correct"] is True
    assert res_data2["score"] == 10.0  # 1.0 * weight (10.0)
    assert block.attempts == 2

    # Attempt 3: Should be blocked by max_attempts = 2
    req3 = make_post_request({"selected_ids": new_correct_ids})
    resp3 = block.submit_answer(req3)
    res_data3 = json.loads(resp3.body)

    assert res_data3["success"] is False
    assert "Maximum attempts reached" in res_data3["error"]
