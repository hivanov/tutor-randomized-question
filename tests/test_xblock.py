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
    block.correct_answers = [
        {"text": "Correct A", "explanation": "Why A is correct"},
        {"text": "Correct B", "explanation": "Why B is correct"},
        {"text": "Correct C", "explanation": "Why C is correct"},
    ]
    block.incorrect_answers = [
        {"text": "Wrong 1", "explanation": "Why 1 is wrong"},
        {"text": "Wrong 2", "explanation": "Why 2 is wrong"},
        {"text": "Wrong 3", "explanation": "Why 3 is wrong"},
        {"text": "Wrong 4", "explanation": "Why 4 is wrong"},
    ]
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
        "correct_answers": [
            {"text": "C1", "explanation": "Exp C1"},
            {"text": "C2", "explanation": "Exp C2"},
            {"text": "C3", "explanation": "Exp C3"},
            {"text": "C4", "explanation": "Exp C4"},
        ],
        "incorrect_answers": [
            {"text": "I1", "explanation": "Exp I1"},
            {"text": "I2", "explanation": "Exp I2"},
            {"text": "I3", "explanation": "Exp I3"},
        ],
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
    assert block.correct_answers[0]["explanation"] == "Exp C1"


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
    # Check that explanation is ONLY returned for the 2 selected choices
    selected_options = [o for o in res_data1["options"] if o["id"] in [correct_ids[0], wrong_ids[0]]]
    unselected_options = [o for o in res_data1["options"] if o["id"] not in [correct_ids[0], wrong_ids[0]]]
    assert all(o["explanation"] != "" for o in selected_options)
    assert all(o["explanation"] == "" for o in unselected_options)

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
    assert "options" in res_data2
    assert len(res_data2["options"]) == 4
    assert res_data2["options"][0]["is_correct"] is not None

    # Attempt 3: Should be blocked by max_attempts = 2
    req3 = make_post_request({"selected_ids": new_correct_ids})
    resp3 = block.submit_answer(req3)
    res_data3 = json.loads(resp3.body)

    assert res_data3["success"] is False
    assert "Maximum attempts reached" in res_data3["error"]


def test_olx_xml_serialization_and_deserialization():
    import xml.etree.ElementTree as ET

    block = create_xblock()
    block.display_name = "OLX Test Question"
    block.prompt = "What is the airspeed velocity of an unladen swallow?"
    block.total_options_count = 4
    block.correct_options_count = 2
    block.weight = 5.0
    block.max_attempts = 3
    block.show_correctness = "always"
    block.explanation = "African or European?"

    node = ET.Element("randomized_question")
    block.add_xml_to_node(node)

    assert node.tag == "randomized_question"
    assert node.get("display_name") == "OLX Test Question"
    assert node.get("prompt") == "What is the airspeed velocity of an unladen swallow?"
    assert node.get("total_options_count") == "4"
    assert node.get("correct_options_count") == "2"
    assert node.get("weight") == "5.0"
    assert node.get("max_attempts") == "3"

    # Test deserialization via parse_xml
    imported_block = RandomizedQuestionXBlock.parse_xml(
        node,
        runtime=block.runtime,
        keys=block.scope_ids,
        id_generator=None,
    )

    assert imported_block.display_name == "OLX Test Question"
    assert imported_block.prompt == "What is the airspeed velocity of an unladen swallow?"
    assert imported_block.total_options_count == 4
    assert imported_block.correct_options_count == 2
    assert imported_block.weight == 5.0
    assert imported_block.max_attempts == 3
    assert len(getattr(imported_block, "correct_answers")) == len(getattr(block, "correct_answers"))
    assert len(getattr(imported_block, "incorrect_answers")) == len(getattr(block, "incorrect_answers"))


def test_parse_xml_with_subelements():
    import xml.etree.ElementTree as ET

    xml_str = """
    <randomized_question url_name="prob1" display_name="Sample Problem"
        total_options_count="4" correct_options_count="2"
        fail_on_any_wrong="true" fail_if_not_all_correct="true"
        grading_default_score="0.0" weight="2.0" max_attempts="3"
        show_correctness="always">
      <prompt>Choose the correct answers:</prompt>
      <explanation>Detailed explanation here.</explanation>
      <correct_answers>
        <item><text>C1</text><explanation>Exp 1</explanation></item>
        <item><text>C2</text><explanation>Exp 2</explanation></item>
      </correct_answers>
      <incorrect_answers>
        <item><text>I1</text><explanation>Exp W1</explanation></item>
        <item><text>I2</text><explanation>Exp W2</explanation></item>
      </incorrect_answers>
      <grading_cases>
        <item id="c1" description="Full score" condition_type="all_correct" max_wrong_allowed="0" score_fraction="1.0" feedback="Great!" />
      </grading_cases>
    </randomized_question>
    """
    node = ET.fromstring(xml_str)
    block = create_xblock()
    imported = RandomizedQuestionXBlock.parse_xml(node, runtime=block.runtime, keys=block.scope_ids)
    assert imported.display_name == "Sample Problem"
    assert imported.prompt == "Choose the correct answers:"
    assert imported.explanation == "Detailed explanation here."
    assert imported.total_options_count == 4
    assert imported.correct_options_count == 2
    assert imported.weight == 2.0
    assert len(getattr(imported, "correct_answers")) == 2
    assert len(getattr(imported, "incorrect_answers")) == 2
    assert len(getattr(imported, "grading_cases")) == 1


