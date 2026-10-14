"""
Standalone Open edX XBlock Integration Server for Playwright E2E Testing and Video Recording.

Implements real Studio authoring, student runtimes with persistent user state,
and teacher analytics dashboard.
"""

import http.server
import json
import os
import threading
from typing import Any

from randomized_question_xblock.engine import CaseGradingEvaluator, PoolSampler
from randomized_question_xblock.models import (
    ClientOption,
    ConditionType,
    GradingCase,
    ShowCorrectnessMode,
    StudentSubmissionPayload,
    StudentSubmitResponse,
    StudioSettingsPayload,
    StudioSubmitResponse,
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "randomized_question_xblock", "static")


class ProblemState:
    """In-memory persistent state for integration testing."""

    def __init__(self) -> None:
        self.settings = StudioSettingsPayload(
            display_name="Distributed Systems & Concurrency Problem",
            prompt="Select all true statements regarding distributed consensus and raft protocol:",
            correct_answers=[
                "Raft ensures state machine safety across leader terms.",
                "Log replication requires an acknowledgment from a strict majority (quorum).",
                "Heartbeats prevent follower nodes from timing out and starting elections.",
            ],
            incorrect_answers=[
                "Two distinct leaders can be elected in the same term.",
                "Followers can append uncommitted entries without leader coordination.",
                "Raft requires all nodes in the cluster to be online to achieve consensus.",
            ],
            total_options_count=4,
            correct_options_count=2,
            fail_on_any_wrong=True,
            fail_if_not_all_correct=True,
            grading_default_score=0.0,
            grading_cases=[
                GradingCase(
                    id="case_all_correct",
                    description="Full credit: All correct with zero wrong choices",
                    condition_type=ConditionType.ALL_CORRECT,
                    score_fraction=1.0,
                    feedback="Perfect! All consensus statements were correctly identified.",
                ),
                GradingCase(
                    id="case_partial_credit",
                    description="Partial credit (1 correct, 0 wrong)",
                    condition_type=ConditionType.EXACT_CORRECT,
                    condition_value=1,
                    score_fraction=0.5,
                    feedback="Partial credit: 1 correct statement identified, but 1 was missed.",
                ),
            ],
            weight=10.0,
            max_attempts=2,
            show_correctness=ShowCorrectnessMode.ALWAYS,
            explanation="Raft requires a strict majority quorum and guarantees leader election safety per term.",
        )
        self.student_states: dict[str, dict[str, Any]] = {}
        self.submissions_log: list[dict[str, Any]] = []

    def get_or_create_student_state(self, student_id: str) -> dict[str, Any]:
        if student_id not in self.student_states:
            options = PoolSampler.sample_and_shuffle(
                correct_pool=self.settings.correct_answers,
                incorrect_pool=self.settings.incorrect_answers,
                t=self.settings.total_options_count,
                c=self.settings.correct_options_count,
                seed=f"{student_id}:attempt_0",
            )
            self.student_states[student_id] = {
                "attempts": 0,
                "score": 0.0,
                "raw_score_fraction": 0.0,
                "completed": False,
                "last_feedback": "",
                "selected_ids": [],
                "options": options,
            }
        return self.student_states[student_id]


STATE = ProblemState()


class XBlockTestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress verbose HTTP server logs

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        if path == "/studio":
            self._serve_studio_page()
        elif path.startswith("/student/"):
            student_id = path.split("/")[2] or "student_1"
            self._serve_student_page(student_id)
        elif path == "/dashboard":
            self._serve_dashboard_page()
        elif path.startswith("/static/"):
            self._serve_static_file(path[len("/static/") :])
        else:
            self.send_error(404, "Page Not Found")

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        data = json.loads(body) if body else {}

        if path == "/api/studio/save":
            self._handle_studio_save(data)
        elif path.startswith("/api/student/"):
            parts = path.split("/")
            student_id = parts[3]
            action = parts[4] if len(parts) > 4 else "submit"
            if action == "submit":
                self._handle_student_submit(student_id, data)
            elif action == "reset":
                self._handle_student_reset(student_id)
            else:
                self.send_error(400, "Unknown student action")
        else:
            self.send_error(404, "Unknown API endpoint")

    def _serve_static_file(self, rel_path: str) -> None:
        full_path = os.path.join(STATIC_DIR, rel_path)
        if not os.path.exists(full_path):
            self.send_error(404, f"Static file {rel_path} not found")
            return

        content_type = "text/plain"
        if rel_path.endswith(".css"):
            content_type = "text/css"
        elif rel_path.endswith(".js"):
            content_type = "application/javascript"
        elif rel_path.endswith(".html"):
            content_type = "text/html"

        with open(full_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_studio_page(self) -> None:
        html_path = os.path.join(STATIC_DIR, "html", "studio_view.html")
        with open(html_path, encoding="utf-8") as f:
            template = f.read()

        context_json = json.dumps(STATE.settings.model_dump())

        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Open edX Studio - Problem Authoring</title>
    <link rel="stylesheet" href="/static/css/randomized_question_studio.css">
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="/static/js/randomized_question_studio.js"></script>
    <style>
        body {{ background: #f0f4f8; margin: 0; padding: 0; font-family: -apple-system, sans-serif; }}
        .studio-topbar {{ background: #0075b4; color: white; padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; }}
        .studio-container {{ max-width: 1000px; margin: 24px auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden; }}
    </style>
</head>
<body>
    <div class="studio-topbar">
        <div style="font-weight: 700; font-size: 1.15rem;">Open edX Studio &mdash; Course Authoring Mode</div>
        <div>Course: <strong>CS701/DistSys</strong> &bull; Unit: <strong>Consensus Evaluation</strong></div>
    </div>
    <div class="studio-container">
        {template}
    </div>
    <script>
        var mockRuntime = {{
            handlerUrl: function(el, action) {{
                return '/api/studio/save';
            }},
            notify: function(event, payload) {{
                console.log('Studio Event:', event, payload);
            }}
        }};
        $(document).ready(function() {{
            RandomizedQuestionStudioView(mockRuntime, $('.randomized-question-studio')[0], {context_json});
        }});
    </script>
</body>
</html>"""

        self._send_html(full_html)

    def _serve_student_page(self, student_id: str) -> None:
        html_path = os.path.join(STATIC_DIR, "html", "student_view.html")
        with open(html_path, encoding="utf-8") as f:
            template = f.read()

        st = STATE.get_or_create_student_state(student_id)
        client_options = [ClientOption(id=opt.id, text=opt.text).model_dump() for opt in st["options"]]

        init_data = {
            "display_name": STATE.settings.display_name,
            "prompt": STATE.settings.prompt,
            "options": client_options,
            "selected_ids": st["selected_ids"],
            "attempts": st["attempts"],
            "max_attempts": STATE.settings.max_attempts,
            "attempts_remaining": max(0, STATE.settings.max_attempts - st["attempts"]),
            "weight": STATE.settings.weight,
            "score": st["score"],
            "raw_score_fraction": st["raw_score_fraction"],
            "completed": st["completed"],
            "last_feedback": st["last_feedback"],
            "show_correctness": STATE.settings.show_correctness.value,
            "explanation": STATE.settings.explanation
            if (st["completed"] and STATE.settings.show_correctness == ShowCorrectnessMode.ALWAYS)
            else "",
            "is_single_choice": (STATE.settings.correct_options_count == 1 and STATE.settings.total_options_count == 2),
        }

        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Open edX LMS - Student Evaluation</title>
    <link rel="stylesheet" href="/static/css/randomized_question.css">
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="/static/js/randomized_question.js"></script>
    <style>
        body {{ background: #f8fafc; margin: 0; padding: 0; font-family: -apple-system, sans-serif; }}
        .lms-topbar {{ background: #1e293b; color: white; padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; }}
        .lms-container {{ max-width: 900px; margin: 24px auto; }}
        .user-pill {{ background: #334155; padding: 4px 10px; border-radius: 20px; font-size: 0.85rem; }}
    </style>
</head>
<body>
    <div class="lms-topbar">
        <div style="font-weight: 700; font-size: 1.15rem;">Open edX LMS &mdash; Course Learning View</div>
        <div>Learner ID: <span class="user-pill">{student_id}</span></div>
    </div>
    <div class="lms-container">
        {template}
    </div>
    <script>
        var studentRuntime = {{
            elementId: 'rq_elem_{student_id}',
            handlerUrl: function(el, action) {{
                if (action === 'submit_answer') return '/api/student/{student_id}/submit';
                if (action === 'reset_problem') return '/api/student/{student_id}/reset';
                return '/';
            }}
        }};
        $(document).ready(function() {{
            RandomizedQuestionStudentView(studentRuntime, $('.randomized-question-block')[0], {json.dumps(init_data)});
        }});
    </script>
</body>
</html>"""

        self._send_html(full_html)

    def _serve_dashboard_page(self) -> None:
        total_sub = len(STATE.submissions_log)
        passed_sub = sum(1 for s in STATE.submissions_log if s["is_correct"])
        partial_sub = sum(1 for s in STATE.submissions_log if s["score"] > 0 and not s["is_correct"])
        failed_sub = sum(1 for s in STATE.submissions_log if s["score"] == 0)

        rows_html = ""
        for s in STATE.submissions_log:
            status_badge = (
                '<span style="background: #22c55e; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 600;">PASS (100%)</span>'
                if s["is_correct"]
                else (
                    '<span style="background: #eab308; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 600;">PARTIAL</span>'
                    if s["score"] > 0
                    else '<span style="background: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 600;">FAIL (0%)</span>'
                )
            )
            rows_html += f"""<tr>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-weight: 600;">{s["student_id"]}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">Attempt {s["attempt"]} of {STATE.settings.max_attempts}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">{status_badge}</td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-weight: 700;">{s["score"]} / {STATE.settings.weight} pts</td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; color: #64748b; font-size: 0.9rem;">{s["matched_case"]}</td>
            </tr>"""

        pass_rate = round((passed_sub / total_sub * 100.0), 1) if total_sub > 0 else 0.0

        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Teacher Grading & Course Analytics Dashboard</title>
    <style>
        body {{ background: #f1f5f9; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #1e293b; }}
        .header {{ background: #0075b4; color: white; padding: 16px 28px; display: flex; justify-content: space-between; align-items: center; }}
        .container {{ max-width: 1000px; margin: 28px auto; padding: 0 16px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
        .stat-card {{ background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        .stat-value {{ font-size: 1.8rem; font-weight: 700; margin-top: 4px; }}
        .stat-card.pass .stat-value {{ color: #16a34a; }}
        .stat-card.partial .stat-value {{ color: #d97706; }}
        .stat-card.fail .stat-value {{ color: #dc2626; }}
        .card {{ background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; }}
        th {{ background: #f8fafc; padding: 10px; font-weight: 600; color: #475569; border-bottom: 2px solid #e2e8f0; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1 style="margin: 0; font-size: 1.3rem;">📊 Open edX Instructor Analytics & Gradebook</h1>
            <div style="font-size: 0.9rem; opacity: 0.9;">Problem: <strong>{STATE.settings.display_name}</strong></div>
        </div>
        <div style="font-size: 0.95rem; background: rgba(255,255,255,0.2); padding: 6px 14px; border-radius: 6px;">
            Total Graded Submissions: <strong>{total_sub}</strong>
        </div>
    </div>
    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <div style="font-size: 0.85rem; color: #64748b; text-transform: uppercase;">Pass Rate</div>
                <div class="stat-value">{pass_rate}%</div>
            </div>
            <div class="stat-card pass">
                <div style="font-size: 0.85rem; color: #64748b; text-transform: uppercase;">100% Pass</div>
                <div class="stat-value">{passed_sub}</div>
            </div>
            <div class="stat-card partial">
                <div style="font-size: 0.85rem; color: #64748b; text-transform: uppercase;">Partial Credit</div>
                <div class="stat-value">{partial_sub}</div>
            </div>
            <div class="stat-card fail">
                <div style="font-size: 0.85rem; color: #64748b; text-transform: uppercase;">Failed (0%)</div>
                <div class="stat-value">{failed_sub}</div>
            </div>
        </div>

        <div class="card">
            <h3 style="margin: 0 0 16px 0; font-size: 1.1rem; color: #0075b4;">Student Submission & Grading Event Logs</h3>
            <table>
                <thead>
                    <tr>
                        <th>Student ID</th>
                        <th>Attempt</th>
                        <th>Grading Outcome</th>
                        <th>Published LMS Score</th>
                        <th>Matched Rule / Failure Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else '<tr><td colspan="5" style="text-align: center; padding: 20px; color: #94a3b8;">No student submissions recorded yet.</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>"""

        self._send_html(full_html)

    def _handle_studio_save(self, data: dict[str, Any]) -> None:
        try:
            payload = StudioSettingsPayload.model_validate(data)
            STATE.settings = payload
            # Reseed student options to reflect new pool settings
            STATE.student_states.clear()
            self._send_json(StudioSubmitResponse(success=True).model_dump())
        except Exception as e:
            self._send_json(StudioSubmitResponse(success=False, error=str(e)).model_dump())

    def _handle_student_submit(self, student_id: str, data: dict[str, Any]) -> None:
        st = STATE.get_or_create_student_state(student_id)
        if st["attempts"] >= STATE.settings.max_attempts:
            resp = StudentSubmitResponse(
                success=False,
                error="Maximum attempts reached for this problem.",
                attempts=st["attempts"],
                max_attempts=STATE.settings.max_attempts,
                attempts_remaining=0,
            )
            self._send_json(resp.model_dump())
            return

        payload = StudentSubmissionPayload.model_validate(data)
        st["selected_ids"] = payload.selected_ids

        eval_res = CaseGradingEvaluator.evaluate(
            selected_ids=set(payload.selected_ids),
            displayed_options=st["options"],
            grading_cases=STATE.settings.grading_cases,
            fail_on_any_wrong=STATE.settings.fail_on_any_wrong,
            fail_if_not_all_correct=STATE.settings.fail_if_not_all_correct,
            default_score=STATE.settings.grading_default_score,
        )

        st["attempts"] += 1
        st["score"] = eval_res.score * STATE.settings.weight
        st["raw_score_fraction"] = eval_res.score
        st["completed"] = True
        st["last_feedback"] = eval_res.feedback

        # Record submission log
        STATE.submissions_log.append(
            {
                "student_id": student_id,
                "attempt": st["attempts"],
                "score": st["score"],
                "is_correct": eval_res.is_correct,
                "matched_case": eval_res.matched_case,
                "feedback": eval_res.feedback,
            }
        )

        show_expl = (
            STATE.settings.explanation if (STATE.settings.show_correctness == ShowCorrectnessMode.ALWAYS) else ""
        )

        resp = StudentSubmitResponse(
            success=True,
            score=st["score"],
            raw_score_fraction=st["raw_score_fraction"],
            max_score=STATE.settings.weight,
            is_correct=eval_res.is_correct,
            feedback=eval_res.feedback,
            matched_case=eval_res.matched_case,
            correctly_selected=eval_res.correctly_selected,
            wrong_selected=eval_res.wrong_selected,
            attempts=st["attempts"],
            max_attempts=STATE.settings.max_attempts,
            attempts_remaining=max(0, STATE.settings.max_attempts - st["attempts"]),
            explanation=show_expl,
        )
        self._send_json(resp.model_dump())

    def _handle_student_reset(self, student_id: str) -> None:
        st = STATE.get_or_create_student_state(student_id)
        if st["attempts"] >= STATE.settings.max_attempts:
            self._send_json({"success": False, "error": "Maximum attempts reached."})
            return

        # Reseed options for fresh random draw
        new_opts = PoolSampler.sample_and_shuffle(
            correct_pool=STATE.settings.correct_answers,
            incorrect_pool=STATE.settings.incorrect_answers,
            t=STATE.settings.total_options_count,
            c=STATE.settings.correct_options_count,
            seed=f"{student_id}:attempt_{st['attempts']}",
        )
        st["options"] = new_opts
        st["selected_ids"] = []
        st["completed"] = False
        st["last_feedback"] = ""

        client_options = [ClientOption(id=opt.id, text=opt.text).model_dump() for opt in new_opts]

        self._send_json(
            {
                "success": True,
                "options": client_options,
                "attempts": st["attempts"],
                "max_attempts": STATE.settings.max_attempts,
            }
        )

    def _send_html(self, html_content: str) -> None:
        encoded = html_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, data: dict[str, Any]) -> None:
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class IntegrationTestServer:
    def __init__(self, port: int = 8899) -> None:
        self.port = port
        self.server = http.server.HTTPServer(("127.0.0.1", self.port), XBlockTestHandler)
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
