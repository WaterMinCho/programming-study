# -*- coding: utf-8 -*-
"""새 전용 환경에 화면 도구를 설치하고 첫 실행·작은 창 검사를 수행함."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CASES = (
    "tests.test_gui.FirstRunTest.test_from_first_run_to_regrade",
    "tests.test_gui.HomeAndGitTest.test_tool_update_at_start_restarts",
    "tests.test_gui.HomeAndGitTest.test_tool_update_during_learning_waits_for_restart_choice",
    "tests.test_gui.HomeAndGitTest.test_blocked_startup_update_does_not_restart_in_a_loop",
    "tests.test_gui.HomeAndGitTest.test_startup_update_backup_is_shown_before_restarting",
    "tests.test_gui_hub.HubScreenTest.test_subject_navigation_fits_a_small_window_at_the_largest_text_size",
    "tests.test_gui_navigation.NavigationTest.test_sidebar_labels_and_keyboard_navigation_fit_both_themes_at_max_text",
    "tests.test_gui_identity.IdentityGuiTest.test_unverified_existing_device_is_prompted_and_fits_max_text_both_themes",
    "tests.test_gui_identity.IdentityGuiTest.test_team_statistics_switch_period_and_are_hidden_for_other_users",
    "tests.test_gui_identity.TeamDashboardTest.test_summary_and_chart_reflow_at_max_text_in_both_themes",
    "tests.test_gui_dialogs.DialogTest.test_pending_preserves_pixels_focus_selection_scroll_and_actions",
    "tests.test_gui_dialogs.DialogTest.test_identity_footer_and_code_fit_max_text_both_themes",
    "tests.test_gui_dialogs.DialogTest.test_long_message_keeps_all_actions_outside_body_scroll",
    "tests.test_gui_onboarding.OnboardingTest.test_visible_controls_fit_and_switch_without_activating_targets",
    "tests.test_gui_ai_courses.CourseGuiTest.test_course_switch_keeps_participant_old_cursor_and_scoped_lists",
    "tests.test_gui_ai_courses.CourseGuiTest.test_course_tab_and_content_commit_together_at_max_text_in_both_themes",
    "tests.test_gui_ai_courses.CourseGuiTest.test_application_steps_keep_image_ratio_at_max_text_and_both_themes",
    "tests.test_gui_ai_courses.CourseGuiTest.test_version_notice_fits_small_window_max_text_and_both_themes",
    "tests.test_gui_ai_courses.CourseGuiTest.test_learning_answers_block_clipboard_without_moving_at_max_text_in_both_courses",
    "tests.test_gui_ai_mock.MockPageTest.test_changed_active_exam_offers_a_new_attempt_from_the_start_button",
    "tests.test_gui_ai_mock.MockPageTest.test_missing_draft_recovery_opens_without_resetting_the_clock_or_records",
    "tests.test_gui_ai_mock.MockPageTest.test_theme_and_text_changes_keep_live_answers_and_recolor_the_stem",
    "tests.test_gui_ai_mock.MockPageTest.test_text_changes_resize_live_code_without_resetting_the_answer",
    "tests.test_gui_ai_mock.MockPageTest.test_choice_text_size_returns_to_the_same_size_after_the_first_change",
    "tests.test_gui_submission.ApiSetupTest.test_setup_fits_small_window_max_text_and_both_themes",
    "tests.test_gui_privacy.PrivacyGuiTest.test_consent_fits_small_window_max_text_and_both_themes",
    "tests.test_gui_submission.ApiSetupTest.test_connection_error_keeps_answers_and_shows_message",
)
CLOSED_CASES = frozenset(name for name in CASES if ".HomeAndGitTest." in name)


def gui_check(out):
    from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
    from PyQt6.QtWidgets import QApplication
    from tests import guikit

    captures, closed = [], []

    class Result(unittest.TextTestResult):
        def startTest(self, case):
            super().startTest(case)
            original = case.tearDown

            def finish():
                try:
                    main_window = getattr(case, "win", None)
                    candidates = (getattr(case, "capture_widget", None), getattr(main_window, "dialog", None), main_window)
                    win = next((widget for widget in candidates if widget is not None and widget.isVisible()), None)
                    if win is not None and win.isVisible():
                        guikit.pump(50)
                        stem = case.id().rsplit(".", 1)[-1]
                        shot = win.grab()
                        if shot.isNull() or not shot.save(str(out / (stem + ".png"))):
                            raise RuntimeError("창 그림을 저장하지 못했음")
                        screen = win.screen()
                        native = screen.grabWindow(int(win.winId()))
                        if native.isNull() or not native.save(str(out / (stem + "-native.png"))):
                            raise RuntimeError("운영체제 창 그림을 저장하지 못했음")
                        captures.append({"case": case.id(), "window": [win.width(), win.height()],
                                         "screen_available": [screen.availableGeometry().width(), screen.availableGeometry().height()],
                                         "native_capture_complete": screen.availableGeometry().contains(win.frameGeometry()),
                                         "device_pixel_ratio": win.devicePixelRatioF(),
                                         "widget_image": [shot.width(), shot.height()],
                                         "native_image": [native.width(), native.height()]})
                    elif case.id() in CLOSED_CASES and main_window is not None and not main_window.isVisible():
                        closed.append(case.id())
                finally:
                    original()

            case.tearDown = finish

    suite = unittest.defaultTestLoader.loadTestsFromNames(CASES)
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    launcher_cases = ["tests.test_launcher_shortcut", "tests.test_gui_launcher.IconFileTest", "tests.test_gui_launcher.StartupTest"]
    if sys.platform == "win32":
        from tests.test_gui_launcher import NativeShortcutTest
        NativeShortcutTest.capture_directory = out
        launcher_cases.append("tests.test_gui_launcher.NativeShortcutTest")
    launcher_suite = unittest.defaultTestLoader.loadTestsFromNames(launcher_cases)
    launcher_result = unittest.TextTestRunner(verbosity=2).run(launcher_suite)
    launcher = {"tests": launcher_result.testsRun, "failures": len(launcher_result.failures),
                "errors": len(launcher_result.errors), "skipped": len(launcher_result.skipped),
                "native_windows": sys.platform == "win32",
                "success": launcher_result.wasSuccessful() and not launcher_result.skipped}
    native_ok = sys.platform != "win32" or QApplication.platformName() == "windows"
    report = {"python": platform.python_version(), "platform": platform.platform(), "python_prefix": sys.prefix,
              "qt": QT_VERSION_STR, "pyqt": PYQT_VERSION_STR,
              "qt_platform": QApplication.platformName(), "qt_scale_override": os.environ.get("QT_SCALE_FACTOR", "1"),
              "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(result.skipped),
              "success": result.wasSuccessful() and not result.skipped and native_ok
                         and result.testsRun == len(CASES) and set(closed) == CLOSED_CASES
                         and {item["case"] for item in captures} == set(CASES) - CLOSED_CASES
                         and all(item["native_capture_complete"] for item in captures) and launcher["success"],
              "launcher": launcher,
              "captures": captures,
              "closed_after_transition": closed,
              "limits": "임시 기록·모의 Git 연결을 사용함. 설치 동의 응답을 자동 입력하며 설치 대화상자의 클릭·사용자 PC·Windows 설정의 글자 크기는 검증하지 않음. 실행기의 화면보다 큰 창은 운영체제 캡처에서 잘릴 수 있어 전체 위젯 그림과 구분함. 바로가기는 Shell API의 아이콘 조회와 임시 start.pyw 실행을 검사함. 탐색기의 실제 표시는 검증하지 않음."}
    target = out / "report.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == report
    return 0 if report["success"] else 1


def main():
    parser = argparse.ArgumentParser(description="배포 전 새 환경 설치와 첫 사용을 확인합니다.")
    parser.add_argument("--out", required=True, help="검사 환경·결과를 둘 새 폴더")
    parser.add_argument("--gui", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "report.json").exists():
        parser.error("이전 보고서가 없는 새 폴더를 지정해 주세요.")
    os.chdir(ROOT)
    for name, folder in (("STUDY_AI_HOME", "ai"), ("STUDY_PYTHON_HOME", "python"),
                         ("STUDY_WEB_HOME", "web"), ("STUDY_JOURNEY_CACHE", "journey")):
        os.environ[name] = str(out / "data" / folder)
    if args.gui:
        return gui_check(out)

    import bootstrap
    venv = out / "venv"
    if venv.exists():
        parser.error("새 폴더를 지정해 주세요. 기존 실행 환경은 사용하거나 지우지 않습니다.")
    os.environ["STUDY_VENV"] = str(venv)

    class InstallHost(bootstrap.Host):
        def isatty(self):
            return True

        def ask(self, prompt):
            print(prompt + "y", flush=True)
            return "y"

        def gui_main(self):
            raise RuntimeError("이미 설치된 PyQt6가 없는 새 파이썬에서 실행해 주세요.")

        def call(self, command):
            return subprocess.call([command[0], str(Path(__file__).resolve()), "--gui", "--out", str(out)])

    code = bootstrap.launch(host=InstallHost())
    if code:
        return code
    target = out / "report.json"
    try:
        report = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 1
    if not report.get("success") or os.path.normcase(report.get("python_prefix", "")) != os.path.normcase(str(venv)):
        return 1
    report["fresh_install"] = bootstrap.venv_state(str(venv)) == "venv"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["fresh_install"] else 1


if __name__ == "__main__":
    sys.exit(main())
