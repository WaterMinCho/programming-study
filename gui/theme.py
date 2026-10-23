# -*- coding: utf-8 -*-
"""테마(시스템 · 밝게 · 어둡게) · 글자 크기 단계(보통 · 크게 · 더 크게) · 글꼴 · 색. 화면 코드는 색 값을 직접 적지 않고 color(토큰 이름)으로,
코드 편집기의 색은 editor(토큰 이름)으로 꺼내 씀. 테마가 바뀌면 signals.changed 가 나옴. 직접 그리는 위젯과 HTML 을 만들어 넣는 화면은
이 신호를 받아 다시 그림. 글자 크기 단계는 set_text 가 TYPE 을 그 단계의 값으로 바꾸고, 창(gui/window.py)이 부품의 글꼴을 다시 줌."""
import os
import re
import sys

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QFontInfo, QFontMetricsF, QPalette
from PyQt6.QtWidgets import QApplication

import mdlite

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")  # 같이 배포하는 나눔고딕과 D2Coding
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")  # 체크 상자의 표시(check_light.svg, check_dark.svg)
CLEAR_FONTS = ("NanumGothic", "Nanum Gothic", "Noto Sans KR", "Noto Sans CJK KR")  # 화면 글꼴로 먼저 씀
UI_FONTS = CLEAR_FONTS + ("Malgun Gothic", "Apple SD Gothic Neo")  # 한글이 있는 글꼴
CODE_FONTS = ("D2Coding", "Consolas", "Menlo", "Cascadia Mono", "DejaVu Sans Mono", "Courier New")  # 코드 글꼴. 같이 배포하는 D2Coding 이 먼저 잡힘
UI_PX = 15  # 버튼·목록·안내 글자 크기
CODE_PX = 16  # 편집기 글자 크기(확대 0 일 때)
DOC_PX = 2  # 문제 본문은 mdlite.CSS 의 크기에 이만큼 더함
DOC_LINE, GUIDE_LINE = 1.45, 1.35  # 본문과 안내 글의 줄 간격. 글자 크기의 몇 배인지
# 글자 크기 단계: 이름 → TYPE 의 모든 크기에 더하는 px. 보통은 설계값, 크게는 새로 설치했을 때의 기본. 옛 화면의 문서와 코드 글꼴은
# 이 px 를 확대 단계(doc_css, code_font 의 zoom)로 받음
TEXT_STEPS = ("normal", "large", "larger")
TEXT_PX = {"normal": 0, "large": 2, "larger": 4}
TEXT_DEFAULT = "large"

MODES = {"system": "시스템", "light": "밝게", "dark": "어둡게"}  # 홈의 단추를 누르면 이 순서로 돎
BRAND = ("#2f6bff", "#7b5cff", "#ffffff")  # 아이콘의 바탕 그라데이션 두 색과 글자 색. 테마가 바뀌어도 같음
AVATARS = ("#2a62f0", "#6d4df2", "#0b7f6a", "#b4530a", "#b83280", "#0e7490")  # 팀 현황의 이니셜 원. 글자는 BRAND 의 글자 색

# 글자와 바탕의 대비는 4.5:1 이상으로 맞춤(tests/test_gui.py 의 ThemeTest 가 확인함).
# 회색은 밝게 9개, 어둡게 11개만 쓰고 같은 값을 뜻이 다른 토큰이 나눠 씀(bg·surface_alt·hover·primary_off·info_weak 는 밝게에서 모두 같음).
# 파란색은 누를 수 있는 것, 고른 것, 진행에만 쓰고 제목(heading·doc_heading)은 글자색과 같음
LIGHT = {
    "bg": "#eef1f5", "surface": "#ffffff", "surface_alt": "#eef1f5", "hover": "#eef1f5", "surface_raised": "#ffffff",
    "border": "#cdd3db", "border_strong": "#818a95", "field_edge": "#818a95", "line": "#e0e5eb", "track": "#e0e5eb",
    "scroll": "#cdd3db", "scroll_hover": "#a9b0ba", "focus": "#1d63ed",
    "ink": "#171b22", "heading": "#171b22", "muted": "#464e59", "placeholder": "#616a76", "faint": "#616a76",
    "primary": "#1d63ed", "primary_hover": "#1251cc", "primary_ink": "#ffffff", "primary_off": "#eef1f5", "primary_off_ink": "#616a76",
    "selection": "#e5efff", "selection_ink": "#1251cc", "text_selection": "#c4d8fd",
    "notice_bg": "#fff2d6", "notice_border": "#fff2d6",
    "code_bg": "#e0e5eb", "codebox_bg": "#eef1f5", "table_head": "#eef1f5", "grid": "#cdd3db",
    "doc_heading": "#171b22", "link": "#1d63ed", "indicator_border": "#818a95",
    "ok": "#007840", "wrong": "#c2272d", "blank": "#616a76", "up": "#1d63ed", "retry": "#a1540f",
    "ok_weak": "#e3f8e9", "wrong_weak": "#ffecec", "retry_weak": "#fff2d6", "info": "#464e59", "info_weak": "#eef1f5",
    "series_python": "#0f9b89", "series_algorithm": "#9476ff", "series_web": "#99007a",
    "unit_mastered": "#1f883d", "unit_mastered_ink": "#ffffff", "unit_level2": "#9cd0ff", "unit_level2_ink": "#1f2328",
    "unit_level1": "#f5d776", "unit_level1_ink": "#1f2328", "unit_retry": "#f0883e", "unit_retry_ink": "#1f2328",
    "unit_none": "#e1e5ea", "unit_none_ink": "#57606a", "unit_none_edge": "#818a95",
}
DARK = {
    "bg": "#0e1217", "surface": "#1d2228", "surface_alt": "#282d34", "hover": "#252a30", "surface_raised": "#252a30",
    "border": "#42474d", "border_strong": "#7b8189", "field_edge": "#7b8189", "line": "#33373d", "track": "#33373d",
    "scroll": "#42474d", "scroll_hover": "#595e65", "focus": "#7aa8ff",
    "ink": "#eaf1fa", "heading": "#eaf1fa", "muted": "#c5cbd4", "placeholder": "#9ea3ac", "faint": "#9ea3ac",
    "primary": "#3168e8", "primary_hover": "#2755c7", "primary_ink": "#ffffff", "primary_off": "#282d34", "primary_off_ink": "#9ea3ac",
    "selection": "#1c2f53", "selection_ink": "#c2d8ff", "text_selection": "#294375",
    "notice_bg": "#382810", "notice_border": "#382810",
    "code_bg": "#33373d", "codebox_bg": "#282d34", "table_head": "#282d34", "grid": "#42474d",
    "doc_heading": "#eaf1fa", "link": "#7aa8ff", "indicator_border": "#7b8189",
    "ok": "#5ccb89", "wrong": "#f87e77", "blank": "#9ea3ac", "up": "#7aa8ff", "retry": "#eeb154",
    "ok_weak": "#182f20", "wrong_weak": "#3e1e1c", "retry_weak": "#382810", "info": "#c5cbd4", "info_weak": "#282d34",
    "series_python": "#0aa99b", "series_algorithm": "#8a7cfd", "series_web": "#c231ac",
    "unit_mastered": "#2ea043", "unit_mastered_ink": "#06120a", "unit_level2": "#58a6ff", "unit_level2_ink": "#0b1220",
    "unit_level1": "#d9b44a", "unit_level1_ink": "#0b1220", "unit_retry": "#e2673a", "unit_retry_ink": "#0b1220",
    "unit_none": "#2b323c", "unit_none_ink": "#b7c1cc", "unit_none_edge": "#7b8189",
}
TOKENS = {"light": LIGHT, "dark": DARK}

# 새 화면(첫 화면, 웹 면접 준비)의 글자 단계: 이름 → (글자 크기 px, 줄 높이 px, 굵기). 굵기는 번들 나눔고딕에 있는 400·700 만 씀.
# 한 화면 상태에서 쓰는 크기는 넷 이하. micro 는 직접 그리는 그래프 눈금에만 씀. BASE_TYPE 은 보통 단계의 설계값이고
# TYPE 은 지금 단계의 값(set_text 가 바꿈). 화면 코드는 TYPE 을 읽음
BASE_TYPE = {"display": (36, 44, 700), "title": (28, 36, 700), "headline": (22, 30, 700), "body": (17, 28, 400), "label": (17, 24, 400),
             "caption": (14, 22, 400), "code": (15, 22, 400), "micro": (13, 16, 400)}
TYPE = dict(BASE_TYPE)
SPACE = (4, 8, 12, 16, 24, 32, 48, 64)  # 간격은 이 값만 씀. 1px 선은 간격이 아니라 선으로 셈
RADIUS = {"check": 6, "small": 8, "control": 12, "card": 16}
CONTROL = {"l": 48, "m": 40, "s": 32, "field": 48, "row": 56, "row2": 72, "topbar": 64, "bottombar": 80, "stepper": 56}
SERIES = ("series_python", "series_algorithm", "series_web")  # 7일 그래프와 트랙 이름 앞 점에만 쓰는 트랙 색

# 코드 편집기의 색. 앱 테마가 밝든 어둡든 같은 남색 바탕을 써서 문제 칸과 구분함.
# 바탕(bg)과의 대비는 글자색이 4.5:1 이상, 주석과 줄 번호가 3:1 이상(tests/test_gui.py 의 HighlightTest 가 확인함)
# locked 는 실행·채점 중에 잠긴 동안의 바탕. blank_bg 는 선택 영역(selection)·찾은 곳(find)과 색상이 달라야 빈칸을 선택했는지 보임
EDITOR = {
    "bg": "#253747", "gutter": "#203140", "edge": "#3a5166", "focus": "#6aa5ff", "selection": "#3d6187",
    "locked": "#19252f", "locked_gutter": "#151f28",
    "scroll": "#4a6177", "scroll_hover": "#5f7a93",
    "ink": "#e0e8f0", "line_no": "#7d91a4",
    "keyword": "#ba9cdc", "def": "#e8e078", "builtin": "#6cc4dc", "string": "#7fc18e", "comment": "#8497a9", "number": "#e092c4",
    "decorator": "#f0a868", "self": "#f08c8c", "blank": "#ffe08a", "blank_bg": "#6a3f6e",
    "find": "#665619", "find_ink": "#fff4c4", "find_current": "#ffb454", "find_current_ink": "#17222d",
    "bar": "#2e4356", "bar_edge": "#4a6177", "field": "#1c2b38", "muted": "#9fb0c0", "faint": "#6f8496", "missing": "#ff8a80",
}

# 채점 결과와 판정: (이름, 토큰). 토큰 이름은 본문 CSS 의 클래스 이름(.ok, .wrong ...)으로도 씀
RESULT = {"ok": ("정답", "ok"), "wrong": ("오답", "wrong"), "blank": ("미응답", "blank")}
VERDICT = {"up": ("진급", "up"), "mastered": ("숙달", "ok"), "done": ("숙달", "ok"), "keep": ("유지", "muted"), "retry": ("재도전", "retry")}
UNIT = {"mastered": "숙달", "level2": "레벨2 진행", "level1": "레벨1 진행", "retry": "재도전", "none": "미진단"}  # 단원 띠. 색은 unit_<상태>, unit_<상태>_ink


def result_label(state):
    """채점 결과를 (이름, 토큰)으로 바꿈. 기록에 남은 skipped·None 은 미응답으로 봄."""
    return RESULT.get(state, RESULT["blank"])


class Signals(QObject):
    changed = pyqtSignal()  # 밝기가 바뀌어 색을 다시 칠한 뒤에 나옴


signals = Signals()
state = {"mode": "system", "scheme": "light", "text": "normal"}  # 고른 테마(MODES 의 키), 지금 칠한 밝기(light · dark), 글자 크기 단계


def scaled_type(step):
    """글자 크기 단계 step 의 TYPE. 크기마다 TEXT_PX 를 더하고, 줄 높이는 글자 크기에 비례해 키운 값을 4 단위로 반올림함
    (본문 17/28 → 19/32 → 21/36, 이름표 17/24 → 19/28 → 21/28). 보통은 설계값 그대로."""
    extra = TEXT_PX[step]
    out = {}
    for role, (size, line, weight) in BASE_TYPE.items():
        out[role] = (size + extra, line if not extra else 4 * round(line * (size + extra) / size / 4), weight)
    return out


def text_px():
    """지금 글자 크기 단계가 모든 크기에 더하는 px. 옛 화면의 문서와 코드 글꼴은 이 값을 확대 단계로 받음."""
    return TEXT_PX[state["text"]]


def color(name):
    """지금 테마에서 토큰의 색 값(#rrggbb)."""
    return TOKENS[state["scheme"]][name]


def qcolor(name):
    return QColor(color(name))


def editor(name):
    """코드 편집기의 색(EDITOR 의 토큰)."""
    return QColor(EDITOR[name])


STYLE = """
QMainWindow, QDialog, QWidget#page, QScrollArea { background: %(bg)s; }
QLabel { color: %(ink)s; }
QLabel#h1 { font-size: 21px; font-weight: 700; color: %(heading)s; }
QLabel#h2 { font-size: 17px; font-weight: 700; color: %(heading)s; }
QLabel#hub_title { font-size: 24px; font-weight: 700; color: %(heading)s; }
QLabel#muted { color: %(muted)s; }
QLabel#big { font-size: 46px; font-weight: 700; color: %(heading)s; }
QLabel#ready { font-size: 26px; font-weight: 700; color: %(heading)s; }
QLabel#me { background: %(primary)s; color: %(primary_ink)s; border-radius: 9px; padding: 1px 8px; font-size: 12px; font-weight: 700; }
QLabel#error { color: %(wrong)s; }
QLabel#warn { color: %(retry)s; }
QLabel#track { font-size: 20px; font-weight: 700; color: %(heading)s; }
QLabel#stat { font-size: 28px; font-weight: 700; color: %(heading)s; }
QLabel#caption { font-size: 13px; color: %(muted)s; }
QLabel#tag { background: %(selection)s; color: %(selection_ink)s; border-radius: 8px; padding: 3px 10px; font-size: 13px; font-weight: 700; }
QLabel#notice { background: %(notice_bg)s; color: %(ink)s; border: 1px solid %(notice_border)s; border-radius: 6px; padding: 8px 12px; }
QFrame#card { background: %(surface)s; border: 1px solid %(border)s; border-radius: 8px; }
QFrame#card[me="true"] { border-color: %(primary)s; }
QFrame#bar { background: %(surface)s; border-top: 1px solid %(border)s; }
QListWidget { background: %(surface)s; color: %(ink)s; border: 1px solid %(border)s; border-radius: 6px; outline: 0; }
QListWidget#plain { border: 0; }
QListWidget::item { padding: 7px 10px; border-bottom: 1px solid %(line)s; }
QListWidget::item:hover { background: %(hover)s; }
QListWidget::item:selected { background: %(selection)s; color: %(selection_ink)s; }
QTextBrowser, QPlainTextEdit, QLineEdit { background: %(surface)s; color: %(ink)s; border: 1px solid %(border)s; border-radius: 6px;
    selection-background-color: %(text_selection)s; selection-color: %(ink)s; placeholder-text-color: %(placeholder)s; }
QPlainTextEdit:focus, QLineEdit:focus { border-color: %(primary)s; }
QPlainTextEdit:disabled, QLineEdit:disabled { background: %(surface_alt)s; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; border: 1px solid %(indicator_border)s; background: %(surface)s; }
QCheckBox::indicator:hover { border-color: %(primary)s; }
QCheckBox::indicator:checked { background: %(primary)s; border-color: %(primary)s; image: url(%(check)s); }
QCheckBox::indicator:disabled { border-color: %(faint)s; background: %(surface_alt)s; }
QCheckBox::indicator:checked:disabled { background: %(primary_off)s; border-color: %(primary_off)s; }
QLineEdit { padding: 6px 8px; }
QPushButton { background: %(surface)s; color: %(ink)s; border: 1px solid %(border_strong)s; border-radius: 6px; padding: 7px 16px; }
QPushButton:hover { background: %(hover)s; }
QPushButton:pressed { background: %(track)s; }
QPushButton:disabled { color: %(faint)s; background: %(bg)s; }
QPushButton#primary { background: %(primary)s; color: %(primary_ink)s; border: 1px solid %(primary_hover)s; font-weight: 700; }
QPushButton#primary:hover, QPushButton#primary:pressed { background: %(primary_hover)s; }
QPushButton#primary:disabled { background: %(primary_off)s; border-color: %(primary_off)s; color: %(primary_off_ink)s; }
QPushButton#primary[big="true"] { font-size: 18px; }
QPushButton#primary[track="true"] { padding: 0 26px; }
QPushButton#quiet { background: transparent; color: %(muted)s; border: 1px solid %(border)s; padding: 4px 12px; }
QPushButton#quiet:hover { background: %(hover)s; color: %(ink)s; }
QProgressBar { background: %(track)s; border: 0; border-radius: 5px; max-height: 10px; min-height: 10px; }
QProgressBar::chunk { background: %(primary)s; border-radius: 5px; }
QToolTip { background: %(surface)s; color: %(ink)s; border: 1px solid %(border_strong)s; padding: 4px 6px; }
QSplitter::handle { background: %(bg)s; }
QMenu { background: %(surface)s; color: %(ink)s; border: 1px solid %(border_strong)s; padding: 4px; }
QMenu::item { padding: 5px 22px; border-radius: 4px; }
QMenu::item:selected { background: %(selection)s; color: %(selection_ink)s; }
QMenu::item:disabled { color: %(faint)s; }
QMenu::separator { height: 1px; background: %(line)s; margin: 4px 6px; }
QScrollBar { background: transparent; border: 0; }
QScrollBar:vertical { width: 14px; margin: 3px; }
QScrollBar:horizontal { height: 14px; margin: 3px; }
QScrollBar::handle { background: %(scroll)s; border-radius: 4px; }
QScrollBar::handle:vertical { min-height: 28px; }
QScrollBar::handle:horizontal { min-width: 28px; }
QScrollBar::handle:hover { background: %(scroll_hover)s; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QAbstractScrollArea::corner { background: transparent; border: 0; }
"""
STYLE += "".join("QLabel#unit_%s { background: %%(unit_%s)s; color: %%(unit_%s_ink)s; border-radius: 4px; font-weight: 700; }\n" % (name, name, name)
                 for name in UNIT)
STYLE += "QLabel#unit_none { border: 1px solid %(unit_none_edge)s; }\n"  # 미진단 칸은 바탕과 색이 비슷해 테두리로 구분함
STYLE += "QListWidget#notes::item:disabled { background: %(table_head)s; color: %(heading)s; }\n"  # 오답 노트의 단원 머리 줄. 고를 수 없게 꺼 둔 줄임

# 새 화면(첫 화면, 웹 면접 준비)의 규칙. 맨 위 위젯에 setProperty("ui", "2") 를 준 화면과 대화상자 아래에만 걸림(옮기지 않은 화면은 그대로).
# 글자 크기는 여기서 주지 않고 gui/kit.py 가 TYPE 으로 글꼴을 직접 줌. 색과 단추·입력칸·체크 상자의 모양만 여기서 줌. 단추의 글자 크기(btn 은
# label, btn_s 는 caption, 편집기 찾기 막대의 단추 code)와 꼬리표 높이(badge)는 스타일시트로만 줄 수 있어 TYPE 에서 꺼내 채움(_style).
# 단추의 min-height 는 테두리 안쪽 높이라 평소 2px 투명 테두리를 빼서 적음(48 = 44 + 2 + 2). 초점이 와도 크기가 바뀌지 않음.
# 크기 속성은 QWidget 의 size 와 부딪히지 않게 scale 로 부름
STYLE_V2 = """
QWidget[ui="2"] { background: %(bg)s; }
QDialog[ui="2"] { background: %(surface_raised)s; }
QWidget[ui="2"] QLabel { color: %(ink)s; background: transparent; }
QWidget[ui="2"] QLabel[tone="secondary"] { color: %(muted)s; }
QWidget[ui="2"] QLabel[tone="tertiary"] { color: %(faint)s; }
QWidget[ui="2"] QLabel[tone="accent"] { color: %(link)s; }
QWidget[ui="2"] QLabel[tone="success"] { color: %(ok)s; }
QWidget[ui="2"] QLabel[tone="warning"] { color: %(retry)s; }
QWidget[ui="2"] QLabel[tone="danger"] { color: %(wrong)s; }
QWidget[ui="2"] QLabel[tone="on_accent"] { color: %(primary_ink)s; }
QWidget[ui="2"] QLabel#badge { border-radius: 12px; padding: 0 8px; min-height: %(badge)spx; max-height: %(badge)spx; background: %(surface_alt)s; color: %(muted)s; }
QWidget[ui="2"] QLabel#badge[tone="accent"] { background: %(selection)s; color: %(selection_ink)s; }
QWidget[ui="2"] QLabel#badge[tone="success"] { background: %(ok_weak)s; color: %(ok)s; }
QWidget[ui="2"] QLabel#badge[tone="warning"] { background: %(retry_weak)s; color: %(retry)s; }
QWidget[ui="2"] QLabel#badge[tone="danger"] { background: %(wrong_weak)s; color: %(wrong)s; }
QWidget[ui="2"] QFrame#card { background: %(surface)s; border: 0; border-radius: 16px; }
QWidget[ui="2"] QFrame#card QFrame#card { background: %(surface_alt)s; border-radius: 12px; }
QWidget[ui="2"] QFrame#well { background: %(surface_alt)s; border: 0; border-radius: 12px; }
QWidget[ui="2"] QFrame#topbar, QWidget[ui="2"] QFrame#bottombar, QWidget[ui="2"] QFrame#stepper { background: %(surface)s; border: 0; }
QWidget[ui="2"] QFrame#topbar[plain="true"] { background: %(bg)s; }
QWidget[ui="2"] QFrame#topbar { border-bottom: 1px solid %(line)s; }
QWidget[ui="2"] QFrame#topbar[plain="true"], QWidget[ui="2"] QFrame#topbar[steps="true"] { border-bottom: 0; }
QWidget[ui="2"] QFrame#stepper { border-bottom: 1px solid %(line)s; }
QWidget[ui="2"] QFrame#bottombar { border-top: 1px solid %(line)s; }
QWidget[ui="2"] QFrame#banner { border: 0; border-radius: 12px; background: %(info_weak)s; }
QWidget[ui="2"] QFrame#banner[tone="warning"] { background: %(retry_weak)s; }
QWidget[ui="2"] QFrame#banner[tone="danger"] { background: %(wrong_weak)s; }
QWidget[ui="2"] QFrame#banner[tone="success"] { background: %(ok_weak)s; }
QWidget[ui="2"] QFrame#banner QLabel#lead { color: %(info)s; }
QWidget[ui="2"] QFrame#banner[tone="warning"] QLabel#lead { color: %(retry)s; }
QWidget[ui="2"] QFrame#banner[tone="danger"] QLabel#lead { color: %(wrong)s; }
QWidget[ui="2"] QFrame#banner[tone="success"] QLabel#lead { color: %(ok)s; }
QWidget[ui="2"] QFrame#banner QPushButton { background: %(surface)s; }
QWidget[ui="2"] QFrame#banner QPushButton:hover, QWidget[ui="2"] QFrame#banner QPushButton:pressed { background: %(line)s; }
QWidget[ui="2"] QFrame#banner QPushButton:disabled { background: transparent; color: %(faint)s; }
QWidget[ui="2"] QFrame#row { background: transparent; border: 0; border-radius: 0; }
QWidget[ui="2"] QFrame#row[over="true"] { background: %(hover)s; }
QWidget[ui="2"] QFrame#row[down="true"] { background: %(surface_alt)s; }
QWidget[ui="2"] QFrame#row[picked="true"] { background: %(selection)s; }
QWidget[ui="2"] QFrame#row[picked="true"] QLabel { color: %(selection_ink)s; }
QWidget[ui="2"] QFrame#row QLabel:disabled { color: %(faint)s; }
QWidget[ui="2"] QFrame#rowline { background: %(line)s; border: 0; }
QWidget[ui="2"] QPushButton { font-size: %(btn)spx; font-weight: 700; border-radius: 12px; padding: 0 20px; min-height: 36px; max-height: 36px;
    min-width: 48px; border: 2px solid transparent; background: %(surface_alt)s; color: %(ink)s; }
QWidget[ui="2"] QPushButton:hover { background: %(track)s; }
QWidget[ui="2"] QPushButton:pressed { background: %(border)s; }
QWidget[ui="2"] QPushButton:focus { border-color: %(focus)s; }
QWidget[ui="2"] QPushButton:disabled { background: %(primary_off)s; color: %(primary_off_ink)s; }
QWidget[ui="2"] QPushButton[scale="l"] { min-height: 44px; max-height: 44px; padding: 0 24px; min-width: 72px; }
QWidget[ui="2"] QPushButton[scale="s"] { min-height: 28px; max-height: 28px; padding: 0 12px; min-width: 32px; font-size: %(btn_s)spx; border-radius: 8px; }
QWidget[ui="2"] QPushButton#primary { background: %(primary)s; color: %(primary_ink)s; border: 2px solid transparent; }
QWidget[ui="2"] QPushButton#primary:hover, QWidget[ui="2"] QPushButton#primary:pressed { background: %(primary_hover)s; }
QWidget[ui="2"] QPushButton#primary:focus { border-color: %(surface)s; }
QWidget[ui="2"] QPushButton#primary:disabled { background: %(primary_off)s; color: %(primary_off_ink)s; }
QWidget[ui="2"] QPushButton#text { background: transparent; color: %(muted)s; padding: 0 12px; }
QWidget[ui="2"] QPushButton#text:hover { background: %(hover)s; color: %(ink)s; }
QWidget[ui="2"] QPushButton#text[onbg="true"]:hover { background: %(line)s; }
QWidget[ui="2"] QPushButton#text:pressed { background: %(track)s; }
QWidget[ui="2"] QPushButton#text:disabled { background: transparent; color: %(faint)s; }
QWidget[ui="2"] QPushButton#text:checked { background: %(selection)s; color: %(selection_ink)s; }
QWidget[ui="2"] QPushButton#danger { background: %(wrong_weak)s; color: %(wrong)s; }
QWidget[ui="2"] QPushButton#danger:hover, QWidget[ui="2"] QPushButton#danger:pressed { background: %(wrong_weak)s; border-color: %(wrong)s; }
QWidget[ui="2"] QPushButton#danger_text { background: transparent; color: %(wrong)s; padding: 0 12px; }
QWidget[ui="2"] QPushButton#danger_text:hover, QWidget[ui="2"] QPushButton#danger_text:pressed { background: %(wrong_weak)s; }
QWidget[ui="2"] QPushButton#chip { font-weight: 400; padding: 0 16px; }
QWidget[ui="2"] QPushButton#chip:checked { background: %(selection)s; color: %(selection_ink)s; font-weight: 700; }
QWidget[ui="2"] QPushButton#chip[onbg="true"] { background: transparent; color: %(muted)s; }
QWidget[ui="2"] QPushButton#chip[onbg="true"]:hover { background: %(line)s; color: %(ink)s; }
QWidget[ui="2"] QPushButton#chip[onbg="true"]:checked { background: %(surface)s; color: %(selection_ink)s; font-weight: 700; }
QWidget[ui="2"] QPushButton#chip:disabled { background: %(primary_off)s; color: %(primary_off_ink)s; }
QWidget[ui="2"] QPushButton#chip:checked:disabled { background: %(selection)s; color: %(faint)s; }
QWidget[ui="2"] QPushButton#chip[onbg="true"]:disabled { background: transparent; color: %(faint)s; }
QWidget[ui="2"] QPushButton#chip[onbg="true"]:checked:disabled { background: %(surface)s; color: %(faint)s; }
QWidget[ui="2"] QPushButton#tab { background: transparent; border-radius: 0; padding: 0; min-width: 0; min-height: 46px; max-height: 46px;
    color: %(faint)s; border: 0; border-bottom: 2px solid transparent; }
QWidget[ui="2"] QPushButton#tab:hover { color: %(muted)s; }
QWidget[ui="2"] QPushButton#tab:checked { color: %(ink)s; border-bottom-color: %(ink)s; }
QWidget[ui="2"] QPushButton#tab:focus { border-bottom-color: %(focus)s; }
QWidget[ui="2"] QLineEdit, QWidget[ui="2"] QPlainTextEdit, QWidget[ui="2"] QTextBrowser { background: %(surface)s; color: %(ink)s;
    border: 1px solid %(field_edge)s; border-radius: 12px; padding: 0 15px; selection-background-color: %(text_selection)s; selection-color: %(ink)s;
    placeholder-text-color: %(faint)s; }
QWidget[ui="2"] QLineEdit { min-height: 46px; max-height: 46px; }
QWidget[ui="2"] QPlainTextEdit { padding: 8px 15px; }
QWidget[ui="2"] QLineEdit:focus, QWidget[ui="2"] QPlainTextEdit:focus { border: 2px solid %(focus)s; padding: 0 14px; }
QWidget[ui="2"] QPlainTextEdit:focus { padding: 7px 14px; }
QWidget[ui="2"] QLineEdit[tone="danger"] { border: 2px solid %(wrong)s; padding: 0 14px; }
QWidget[ui="2"] QLineEdit:disabled, QWidget[ui="2"] QPlainTextEdit:disabled { background: %(surface_alt)s; color: %(muted)s; }
QWidget[ui="2"] QPlainTextEdit#code { border-radius: 12px; padding: 0; }
QWidget[ui="2"] QTextBrowser#plain, QWidget[ui="2"] QPlainTextEdit#plain { border: 0; border-radius: 0; padding: 0; background: transparent; }
QWidget[ui="2"] QCheckBox { color: %(ink)s; spacing: 12px; }
QWidget[ui="2"] QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid %(field_edge)s; border-radius: 6px; background: %(surface)s; }
QWidget[ui="2"] QCheckBox::indicator:hover { border-color: %(primary)s; }
QWidget[ui="2"] QCheckBox::indicator:checked { background: %(primary)s; border-color: %(primary)s; image: url(%(check)s); }
QWidget[ui="2"] QCheckBox::indicator:disabled { border-color: %(border)s; background: %(surface_alt)s; }
QWidget[ui="2"] QCheckBox::indicator:checked:disabled { background: %(primary_off)s; border-color: %(primary_off)s; }
QWidget[ui="2"] QCheckBox:focus { outline: 0; }
QWidget[ui="2"] QProgressBar { background: %(track)s; border: 0; border-radius: 4px; min-height: 8px; max-height: 8px; }
QWidget[ui="2"] QProgressBar::chunk { background: %(link)s; border-radius: 4px; }
QWidget[ui="2"] QProgressBar[tone="success"]::chunk { background: %(ok)s; }
QWidget[ui="2"] QProgressBar[thin="true"] { border-radius: 2px; min-height: 4px; max-height: 4px; }
QWidget[ui="2"] QProgressBar[thin="true"]::chunk { border-radius: 2px; }
QWidget[ui="2"] QProgressBar[tone="warning"]::chunk { background: %(retry)s; }
QWidget[ui="2"] QProgressBar[tone="danger"]::chunk { background: %(wrong)s; }
QWidget[ui="2"] QScrollArea, QWidget[ui="2"] QScrollArea > QWidget > QWidget { background: transparent; }
QWidget[ui="2"] QScrollArea#page, QWidget[ui="2"] QWidget#page { background: %(bg)s; }
QWidget[ui="2"] QFrame#card QScrollArea, QWidget[ui="2"] QFrame#card QScrollArea > QWidget > QWidget { background: %(surface)s; }
QWidget[ui="2"] QFrame#card QScrollArea[flat="true"], QWidget[ui="2"] QFrame#card QScrollArea[flat="true"] > QWidget,
    QWidget[ui="2"] QFrame#card QScrollArea[flat="true"] > QWidget > QWidget { background: transparent; }
QWidget[ui="2"] QSplitter::handle { background: %(bg)s; }
QWidget[ui="2"] QFrame#find QLineEdit { min-height: 0px; max-height: 200px; border-radius: 6px; }
QWidget[ui="2"] QFrame#find QPushButton#tool { min-height: 0px; max-height: 200px; font-size: %(code)spx; }
"""

# 코드 편집기와 그 위에 뜨는 찾기 막대. 앱 테마의 규칙 뒤에 붙여서 두 테마에서 같은 색으로 덮음
EDITOR_STYLE = """
QPlainTextEdit#code { background: %(bg)s; color: %(ink)s; border: 1px solid %(edge)s;
    selection-background-color: %(selection)s; selection-color: %(ink)s; }
QPlainTextEdit#code:focus { border-color: %(focus)s; }
QPlainTextEdit#code:disabled { background: %(locked)s; }
QPlainTextEdit#code QScrollBar::handle { background: %(scroll)s; }
QPlainTextEdit#code QScrollBar::handle:hover { background: %(scroll_hover)s; }
QFrame#find { background: %(bar)s; border: 1px solid %(bar_edge)s; border-radius: 6px; }
QFrame#find QLineEdit { background: %(field)s; color: %(ink)s; border: 1px solid %(bar_edge)s; padding: 3px 6px;
    selection-background-color: %(selection)s; selection-color: %(ink)s; placeholder-text-color: %(muted)s; }
QFrame#find QLineEdit:focus { border-color: %(focus)s; }
QFrame#find QLineEdit[missing="true"] { border-color: %(missing)s; }
QFrame#find QLabel#muted { color: %(muted)s; }
QFrame#find QPushButton#tool { background: transparent; color: %(ink)s; border: 0; border-radius: 4px; padding: 3px 0; min-width: 26px;
    font-weight: 700; }
QFrame#find QPushButton#tool:hover { background: %(bar_edge)s; }
QFrame#find QPushButton#tool:pressed { background: %(scroll_hover)s; }
QFrame#find QPushButton#tool:disabled { background: transparent; color: %(faint)s; }
""" % EDITOR

# 본문 CSS(mdlite.CSS)에 화면이 더하는 것: 결과·판정 글자색과 결과 화면의 구역 띠
DOC_CSS = """
.muted { color: %(muted)s; }
.ok { color: %(ok)s; }
.wrong { color: %(wrong)s; }
.blank { color: %(blank)s; }
.up { color: %(up)s; }
.retry { color: %(retry)s; }
td.band { background-color: %(table_head)s; }
"""

# 새 화면의 문서(웹 면접 준비의 미션 지문·해설·학습 노트·드릴 배경, 알고리즘 여행의 지문·힌트·해설·던전 소개)가 본문 CSS 뒤에 더하는 것.
# 크기는 TYPE 의 body 17/28, h1 22/30, h2 17 700, code 15/22 이고 문단 사이 16. doc_css 가 모든 font-size 에 DOC_PX 와 확대 단계를
# 더하므로 여기 적는 값은 그만큼 뺀 것임. 제목은 글자색과 같은 색(파란 제목 없음). 구역 제목 앞의 가로줄(hr)은 DocView 가 넣고,
# 코드 상자의 바깥 여백·둥근 바탕과 표의 열 폭은 TextPiece 가 정함.
# 줄 높이는 px 로 고정함. 비율로 주면 화면 글꼴에 없어 다른 글꼴로 그리는 글자(−)가 든 문단은 줄마다 그 글꼴의 높이로 벌어짐
WEB_CSS = """
body { font-size: %(wbody)spx; }
p { margin-bottom: 16px; line-height: %(wline)spx; }
p.h1 { font-size: %(wh1)spx; margin-top: 0px; margin-bottom: 8px; line-height: %(wh1line)spx; color: %(ink)s; }
p.h2 { font-size: %(wbody)spx; margin-top: 24px; margin-bottom: 8px; line-height: %(wline)spx; color: %(ink)s; }
p.h3 { font-size: %(wbody)spx; margin-top: 8px; margin-bottom: 4px; line-height: %(wline)spx; color: %(ink)s; }
hr { background-color: %(track)s; margin-top: 16px; margin-bottom: 16px; }
ul, ol { margin-top: 0px; margin-bottom: 8px; }
li { margin-bottom: 8px; line-height: %(wline)spx; }
li p { margin-bottom: 8px; }
code { font-size: %(wcode)spx; background-color: %(track)s; }  /* doc_css 의 line 은 줄 간격 값이라 색은 track 으로 씀 */
pre { font-size: %(wcode)spx; line-height: %(wcodeline)spx; }
td.codebox { background-color: transparent; border: 0px; padding: 12px 16px; }  /* 둥근 바탕은 TextPiece.paintEvent 가 칠함 */
td.quote { padding: 12px 16px 4px 16px; }
table.grid { margin-top: 8px; margin-bottom: 8px; }
table.grid th { padding: 8px 12px; }
table.grid td { line-height: %(wline)spx; padding: 4px 12px 8px 12px; }
"""

_fonts = {}


def _installed(names):
    if "all" not in _fonts:
        _fonts["all"] = set(QFontDatabase.families())
    return [name for name in names if name in _fonts["all"]]


def system_scheme():
    """운영체제가 어두운 모드면 dark, 아니거나 알 수 없으면(Qt 6.5 미만 포함) light."""
    hints = QApplication.instance().styleHints()
    return "dark" if hasattr(hints, "colorScheme") and hints.colorScheme() == Qt.ColorScheme.Dark else "light"


def apply(app, mode="system"):
    """시작할 때 한 번 부름. 글꼴과 스타일을 정하고 mode 의 테마를 칠함."""
    app.setStyle("Fusion")
    for name in sorted(os.listdir(FONT_DIR)) if os.path.isdir(FONT_DIR) else []:  # 어느 컴퓨터에서나 같은 글꼴로 보이게 등록함
        if name.endswith(".ttf"):
            QFontDatabase.addApplicationFont(os.path.join(FONT_DIR, name))
    _fonts.clear()
    family = _installed(CLEAR_FONTS) or (_installed(("Malgun Gothic",)) if sys.platform == "win32" else [])
    font = app.font()
    if family:  # 또렷한 글꼴이 있으면 그것을 쓰고, Windows 에서는 굴림 대신 맑은 고딕을 씀
        font.setFamily(family[0])
    font.setPixelSize(UI_PX)
    app.setFont(font)
    hints = app.styleHints()
    if hasattr(hints, "colorSchemeChanged"):  # Qt 6.5 이상. 시스템을 따르는 동안 운영체제 설정이 바뀌면 따라감
        hints.colorSchemeChanged.connect(_follow_system)
    set_mode(mode, force=True)


def set_mode(mode, force=False):
    """테마를 고름(MODES 의 키, 모르는 값은 system). 밝기가 달라지면 창 전체를 다시 칠하고 signals.changed 를 냄."""
    state["mode"] = mode = mode if mode in MODES else "system"
    hints = QApplication.instance().styleHints()
    if hasattr(hints, "setColorScheme"):  # Qt 6.8 이상. 제목 표시줄처럼 운영체제가 그리는 부분도 맞춤
        if mode == "system":
            hints.unsetColorScheme()
        else:
            hints.setColorScheme(Qt.ColorScheme.Dark if mode == "dark" else Qt.ColorScheme.Light)
    scheme = system_scheme() if mode == "system" else mode
    if force or scheme != state["scheme"]:
        _paint(scheme)


def _follow_system(*_):
    if state["mode"] == "system" and system_scheme() != state["scheme"]:
        _paint(system_scheme())


def _paint(scheme):
    _style(scheme)
    signals.changed.emit()


def _style(scheme):
    """팔레트와 스타일시트를 scheme 의 색과 지금 TYPE 의 크기로 다시 입힘."""
    state["scheme"] = scheme
    app = QApplication.instance()
    palette = QPalette(qcolor("surface"), qcolor("bg"))  # 버튼 색과 창 색을 주면 나머지 음영은 Qt 가 계산함
    role = QPalette.ColorRole
    for part, name in ((role.Window, "bg"), (role.WindowText, "ink"), (role.Base, "surface"), (role.AlternateBase, "surface_alt"),
                       (role.Text, "ink"), (role.Button, "surface"), (role.ButtonText, "ink"), (role.Highlight, "text_selection"),
                       (role.HighlightedText, "ink"), (role.PlaceholderText, "placeholder"), (role.ToolTipBase, "surface"),
                       (role.ToolTipText, "ink"), (role.Link, "link")):
        palette.setColor(part, qcolor(name))
    app.setPalette(palette)
    tokens = style_tokens(scheme)
    app.setStyleSheet(STYLE % tokens + STYLE_V2 % tokens + EDITOR_STYLE)


def style_tokens(scheme):
    """스타일시트에 채우는 값: scheme 의 색, 체크 표시 그림, 단추 글자 크기(btn 은 label, btn_s 는 caption, code 는 찾기 막대 단추),
    꼬리표 높이(caption 줄 높이 + 2)."""
    check = os.path.join(ICON_DIR, "check_%s.svg" % scheme).replace("\\", "/")  # 스타일시트의 url() 은 / 로 적음
    return dict(TOKENS[scheme], check=check, btn=TYPE["label"][0], btn_s=TYPE["caption"][0], code=TYPE["code"][0], badge=TYPE["caption"][1] + 2)


def set_text(step):
    """글자 크기 단계를 고름(TEXT_STEPS 의 이름, 모르는 값은 기본). TYPE 을 그 단계의 값으로 바꾸고 스타일시트를 다시 입힘.
    이미 만든 부품의 글꼴은 바꾸지 않으므로 창이 kit.refont 로 다시 줌. 바뀌었으면 True."""
    step = step if step in TEXT_PX else TEXT_DEFAULT
    if step == state["text"] and TYPE == scaled_type(step):
        return False
    state["text"] = step
    TYPE.clear()
    TYPE.update(scaled_type(step))
    if QApplication.instance() is not None:
        _style(state["scheme"])
    return True


def font(role, bold=None):
    """TYPE 의 글자 단계 role 로 만든 화면 글꼴. bold 를 주면 굵기를 그것으로 바꿈(강조한 본문·이름표)."""
    size, _, weight = TYPE[role]
    f = QFont(QApplication.font())
    f.setPixelSize(size)
    f.setBold(weight >= 700 if bold is None else bool(bold))
    return f


def line_pct(times, font=None):
    """줄 간격이 글자 크기의 times 배가 되게 하는 줄 높이 백분율. Qt 는 이 값을 글꼴의 줄 높이에 곱하는데,
    같은 글꼴도 운영체제에 따라 줄 높이가 글자 크기의 1.0~1.3 배로 다르게 읽혀서 화면 글꼴(font 를 주면 그 글꼴)로 재서 맞춤."""
    font = font or QApplication.font()
    return max(100, round(100 * times * QFontInfo(font).pixelSize() / QFontMetricsF(font).lineSpacing()))


def code_families():
    """고정폭 글꼴 하나와 한글 대체 글꼴. 플랫폼 기본 고정폭이 실제로는 고정폭이 아닌 환경이 있어 설치된 글꼴에서 이름으로 고름."""
    mono = _installed(CODE_FONTS)[:1] or [QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()]
    return mono + _installed(UI_FONTS)[:1]


def code_font(zoom=0):
    font = QFont()
    font.setFamilies(code_families())
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    font.setPixelSize(CODE_PX + zoom)
    return font


def doc_css(zoom=0, extra="", own_body=False):
    """문제 본문용 CSS. 지금 테마의 색을 채우고, 글자 크기를 확대 단계만큼 키우고, 코드 글꼴을 설치된 글꼴로 바꿈.
    extra 는 본문 CSS 뒤에 붙일 규칙(WEB_CSS). own_body 면 mdlite 의 body 글자 크기를 빼서 extra 의 body 크기가 먹게 함.
    Qt 리치 텍스트는 body 의 font-size 가 둘이면 앞의 것을 씀. WEB_CSS 의 크기는 지금 단계의 TYPE 값이라 확대 단계를 미리 뺌."""
    base = re.sub(r"(?m)^(body \{[^}]*?)font-size: \d+px; ?", r"\1", mdlite.CSS) if own_body else mdlite.CSS
    css = (base + DOC_CSS + extra) % dict(TOKENS[state["scheme"]], line=line_pct(DOC_LINE),
                                                wbody=TYPE["body"][0] - DOC_PX - zoom, wline=TYPE["body"][1], wh1=TYPE["headline"][0] - DOC_PX - zoom,
                                                wh1line=TYPE["headline"][1], wcode=TYPE["code"][0] - DOC_PX - zoom, wcodeline=TYPE["code"][1])
    css = re.sub(r"font-size: (\d+)px", lambda m: "font-size: %dpx" % (int(m.group(1)) + DOC_PX + zoom), css)
    families = ", ".join("'%s'" % name for name in code_families())
    return re.sub(r"font-family: [^;]+;", "font-family: %s;" % families, css)


def web_css():
    """새 규칙(ui="2") 화면의 문서용 CSS. doc_css 에 WEB_CSS 를 더함. 크기는 지금 글자 크기 단계의 TYPE 값."""
    return doc_css(text_px(), WEB_CSS, own_body=True)


def journey_css():
    """알고리즘 여행의 지문·힌트·해설과 던전 소개용 CSS. 웹 면접 준비 문서와 같은 규칙(web_css)을 씀."""
    return web_css()


def result_css():
    """알고리즘 여행 결과 칸용 CSS. web_css 에서 문단 아래 여백만 4 로 줄여 테스트 한 줄이 문단 하나인 결과가 길게 늘어지지 않게 함."""
    return web_css() + "p { margin-bottom: 4px; } p.h3 { margin-top: 16px; margin-bottom: 4px; }"
