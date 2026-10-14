"""
Playwright End-to-End Video Recording for Open edX Randomized Question XBlock.

Records a complete video displaying:
- Scene 1: Teacher Studio Problem Authoring & Case Rule Setup
- Scene 2: Student 1 - 100% Correct Submission (Immediate Results & Explanation)
- Scene 3: Student 2 - Partial Credit Submission (Several correct, no incorrect)
- Scene 4: Student 3 - Strict Fail (One incorrect on top of all correct)
- Scene 5: Student 4 - Strict Fail (All incorrect answers)
- Scene 6: Student 5 - Under-selection Validation (0 options selected)
- Scene 7: Student 6 - Multi-Attempt Retries & Max Attempt Exhaustion Locking
- Scene 8: Student 7 - Delayed Correctness Mode (Answers revealed after test)
- Scene 9: Teacher Course Dashboard (Pass/Fail Analytics & Submission Event Logs)
"""

import os
import shutil
import subprocess
import time

from playwright.sync_api import sync_playwright

from randomized_question_xblock.models import ShowCorrectnessMode
from tests.integration.server import STATE, IntegrationTestServer

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")
TEMP_VIDEO_DIR = os.path.join(ARTIFACTS_DIR, "raw_video_tmp")
FINAL_MP4 = os.path.join(ARTIFACTS_DIR, "randomized_question_e2e.mp4")

os.makedirs(TEMP_VIDEO_DIR, exist_ok=True)


def record_video() -> str:
    server = IntegrationTestServer(port=8899)
    server.start()
    time.sleep(0.5)

    base_url = "http://127.0.0.1:8899"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=TEMP_VIDEO_DIR,
            record_video_size={"width": 1280, "height": 900},
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        # Helper for banner overlay
        def show_scene_banner(title: str, subtitle: str, duration_s: float = 2.0) -> None:
            page.evaluate(
                f"""() => {{
                let existing = document.getElementById('scene-overlay-banner');
                if (existing) existing.remove();
                let banner = document.createElement('div');
                banner.id = 'scene-overlay-banner';
                banner.style.cssText = 'position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #1e293b; color: #f8fafc; padding: 14px 28px; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.25); z-index: 99999; text-align: center; font-family: sans-serif; border-left: 6px solid #38bdf8; pointer-events: none;';
                banner.innerHTML = '<div style="font-size: 1.15rem; font-weight: bold; margin-bottom: 4px;">{title}</div><div style="font-size: 0.9rem; color: #94a3b8;">{subtitle}</div>';
                document.body.appendChild(banner);
            }}"""
            )
            time.sleep(duration_s)
            page.evaluate(
                """() => {
                let banner = document.getElementById('scene-overlay-banner');
                if (banner) banner.remove();
            }"""
            )

        # -------------------------------------------------------------
        # SCENE 1: Teacher Studio Authoring
        # -------------------------------------------------------------
        print("[Scene 1] Teacher Studio: Configuring Pools, Constraints & Piecewise Rules...")
        page.goto(f"{base_url}/studio")
        page.wait_for_selector(".randomized-question-studio")
        show_scene_banner(
            "Scene 1: Teacher Studio Authoring",
            "Configuring Pools C & I, Subset Parameters (t=4, c=2), and Custom Grading Function g(x)",
            3.0,
        )

        page.click(".btn-add-c")
        page.fill(
            ".list-pool-c .pool-item-row:last-child input",
            "Raft uses randomized election timers to avoid split votes.",
        )
        time.sleep(1.0)
        page.click(".btn-save")
        page.wait_for_selector(".save-status:has-text('Saved successfully!')")
        time.sleep(2.0)

        # -------------------------------------------------------------
        # SCENE 2: Student 1 (100% Pass)
        # -------------------------------------------------------------
        print("[Scene 2] Student 1: 100% Correct Submission (All correct, 0 wrong)...")
        page.goto(f"{base_url}/student/student_1_perfect")
        page.wait_for_selector(".randomized-question-block")
        show_scene_banner(
            "Scene 2: Student 1 (100% Pass)",
            "Selecting all 2 correct choices and 0 wrong choices",
            2.5,
        )

        st1_opts = STATE.get_or_create_student_state("student_1_perfect")["options"]
        for cid in [o.id for o in st1_opts if o.is_correct]:
            page.check(f"input[value='{cid}']")
            time.sleep(0.5)

        time.sleep(0.5)
        page.click(".btn-submit")
        page.wait_for_selector(".feedback-alert.alert-success")
        time.sleep(2.5)

        # -------------------------------------------------------------
        # SCENE 3: Student 2 (Partial Credit)
        # -------------------------------------------------------------
        print("[Scene 3] Student 2: Partial Credit Submission (1 correct, 0 wrong)...")
        page.goto(f"{base_url}/student/student_2_partial")
        page.wait_for_selector(".randomized-question-block")
        show_scene_banner(
            "Scene 3: Student 2 (Partial Credit)",
            "Selecting 1 correct choice and 0 wrong choices (g(x) = 50%)",
            2.5,
        )

        st2_opts = STATE.get_or_create_student_state("student_2_partial")["options"]
        c_id = [o.id for o in st2_opts if o.is_correct][0]
        page.check(f"input[value='{c_id}']")
        time.sleep(0.5)

        page.click(".btn-submit")
        page.wait_for_selector(".feedback-alert.alert-warning")
        time.sleep(2.5)

        # -------------------------------------------------------------
        # SCENE 4: Student 3 (Strict Fail: Wrong choice on top of all correct)
        # -------------------------------------------------------------
        print("[Scene 4] Student 3: Strict Fail (Selected 2 correct + 1 wrong)...")
        page.goto(f"{base_url}/student/student_3_wrong_on_top")
        page.wait_for_selector(".randomized-question-block")
        show_scene_banner(
            "Scene 4: Student 3 (Strict Fail)",
            "Selected all correct choices PLUS 1 wrong choice -> Rule 1 triggers g(x)=0",
            2.5,
        )

        st3_opts = STATE.get_or_create_student_state("student_3_wrong_on_top")["options"]
        for cid in [o.id for o in st3_opts if o.is_correct]:
            page.check(f"input[value='{cid}']")
            time.sleep(0.4)
        wid = [o.id for o in st3_opts if not o.is_correct][0]
        page.check(f"input[value='{wid}']")
        time.sleep(0.5)

        page.click(".btn-submit")
        page.wait_for_selector(".feedback-alert.alert-danger")
        time.sleep(2.5)

        # -------------------------------------------------------------
        # SCENE 5: Student 4 (Strict Fail: All wrong choices)
        # -------------------------------------------------------------
        print("[Scene 5] Student 4: Strict Fail (All wrong choices selected)...")
        page.goto(f"{base_url}/student/student_4_all_wrong")
        page.wait_for_selector(".randomized-question-block")
        show_scene_banner(
            "Scene 5: Student 4 (All Wrong)",
            "Selecting only incorrect choices -> Evaluates to 0%",
            2.5,
        )

        st4_opts = STATE.get_or_create_student_state("student_4_all_wrong")["options"]
        for wid in [o.id for o in st4_opts if not o.is_correct]:
            page.check(f"input[value='{wid}']")
            time.sleep(0.4)

        page.click(".btn-submit")
        page.wait_for_selector(".feedback-alert.alert-danger")
        time.sleep(2.5)

        # -------------------------------------------------------------
        # SCENE 6: Student 5 (Under-Selection / Zero Selection)
        # -------------------------------------------------------------
        print("[Scene 6] Student 5: Under-Selection validation (0 choices)...")
        page.goto(f"{base_url}/student/student_5_under_selected")
        page.wait_for_selector(".randomized-question-block")
        show_scene_banner(
            "Scene 6: Student 5 (Under-Selection)",
            "Attempting to submit with 0 selections -> Client validation alert",
            2.5,
        )

        page.on("dialog", lambda dialog: dialog.accept())
        page.click(".btn-submit")
        time.sleep(2.0)

        # -------------------------------------------------------------
        # SCENE 7: Student 6 (Multi-attempt Retry & Attempt Exhaustion)
        # -------------------------------------------------------------
        print("[Scene 7] Student 6: Multi-attempt Retry lifecycle & Locking upon exhaustion...")
        page.goto(f"{base_url}/student/student_6_retrier")
        page.wait_for_selector(".randomized-question-block")
        show_scene_banner(
            "Scene 7: Multi-Attempt Retry & Exhaustion",
            "Attempt 1: Fail -> Reset & Reseed -> Attempt 2: Fail -> Max Attempts (2/2) Locked",
            3.0,
        )

        # Attempt 1
        st6_opts = STATE.get_or_create_student_state("student_6_retrier")["options"]
        page.check(f"input[value='{[o.id for o in st6_opts if not o.is_correct][0]}']")
        time.sleep(0.5)
        page.click(".btn-submit")
        page.wait_for_selector(".feedback-alert.alert-danger")
        time.sleep(1.5)

        # Reset for Attempt 2
        page.click(".btn-reset")
        time.sleep(1.0)

        # Attempt 2
        st6_opts_att2 = STATE.get_or_create_student_state("student_6_retrier")["options"]
        page.check(f"input[value='{[o.id for o in st6_opts_att2 if not o.is_correct][0]}']")
        time.sleep(0.5)
        page.click(".btn-submit")
        page.wait_for_selector(".feedback-alert.alert-danger")
        time.sleep(2.0)

        # -------------------------------------------------------------
        # SCENE 8: Student 7 (Delayed Correctness Mode - Show Correctness: Past Due)
        # -------------------------------------------------------------
        print("[Scene 8] Student 7: Delayed Correctness Mode (past_due)...")
        # Change mode in server state to past_due
        STATE.settings.show_correctness = ShowCorrectnessMode.PAST_DUE
        page.goto(f"{base_url}/student/student_7_delayed_feedback")
        page.wait_for_selector(".randomized-question-block")
        show_scene_banner(
            "Scene 8: Delayed Correctness (past_due)",
            "Score is recorded, but green/red feedback & explanations are hidden until exam close",
            3.0,
        )

        st7_opts = STATE.get_or_create_student_state("student_7_delayed_feedback")["options"]
        for cid in [o.id for o in st7_opts if o.is_correct]:
            page.check(f"input[value='{cid}']")
        page.click(".btn-submit")
        time.sleep(2.0)

        # Restore show_correctness
        STATE.settings.show_correctness = ShowCorrectnessMode.ALWAYS

        # -------------------------------------------------------------
        # SCENE 9: Teacher Course Dashboard & Grading Analytics
        # -------------------------------------------------------------
        print("[Scene 9] Teacher Dashboard: Live Pass/Fail Rates & Submission Analytics...")
        page.goto(f"{base_url}/dashboard")
        page.wait_for_selector(".stats-grid")
        show_scene_banner(
            "Scene 9: Teacher Course Dashboard",
            "Live Pass/Fail summary rates, attempt logs, and score distributions",
            3.5,
        )
        time.sleep(4.0)

        context.close()
        browser.close()

    server.stop()

    # Move generated WebM/MP4 from Playwright video directory to final MP4 path
    video_files = [f for f in os.listdir(TEMP_VIDEO_DIR) if f.endswith(".webm") or f.endswith(".mp4")]
    if video_files:
        src_video = os.path.join(TEMP_VIDEO_DIR, video_files[0])
        # Transcode to standard high-compatibility H.264 MP4 with ffmpeg
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            src_video,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "fast",
            FINAL_MP4,
        ]
        subprocess.run(ffmpeg_cmd, check=True)
        shutil.rmtree(TEMP_VIDEO_DIR, ignore_errors=True)
        print(f"[Done] Final video recorded and saved to: {FINAL_MP4}")
        return FINAL_MP4
    else:
        raise RuntimeError("No video file generated by Playwright context.")


if __name__ == "__main__":
    record_video()
