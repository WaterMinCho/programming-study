#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""제출 기록에서 과목별 dashboard.svg와 DASHBOARD.md를 만듦.

점수로 정렬하지 않고 ID 순서로 보임. 집계 값과 다음 행동은 subject_analysis의 값만 씀.
"""
import argparse
import html
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import study  # noqa: E402
import subject_analysis as analysis  # noqa: E402

OUT_DIR = os.path.join(study.ROOT, "out")
COLORS = {"available": "#2563eb", "no_record": "#64748b", "unavailable": "#b91c1c"}


def _wrap(text, width=58):
    lines, line, used = [], "", 0
    for char in text:
        size = 2 if unicodedata.east_asian_width(char) in "WF" else 1
        if used + size > width:
            lines.append(line)
            line, used = "", 0
        line += char
        used += size
    return lines + ([line] if line else [])


def render_svg(rows, unavailable=False):
    width, top, card_width, gap = 1080, 92, 508, 16
    metric_rows = max((len(subject.metrics) for row in rows for subject in row.subjects), default=0)
    card_height = max(206, 132 + metric_rows * 21)
    person_height = 44 + card_height * 2 + gap
    height = top + max(1, len(rows)) * person_height + 42
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="Pretendard, Apple SD Gothic Neo, Malgun Gothic, sans-serif">' % (width, height, width, height),
           '<rect width="100%" height="100%" fill="#ffffff"/>']

    def text(x, y, value, size=15, color="#334155", weight="400"):
        out.append('<text x="%d" y="%d" font-size="%d" font-weight="%s" fill="%s">%s</text>' % (x, y, size, weight, color, html.escape(str(value))))

    text(24, 36, "과목별 학습 기록을 확인하세요", 24, "#0f172a", "700")
    sources = {subject.source for row in rows for subject in row.subjects}
    if sources == {"service"}:
        caption = "이 기기 서비스에서 확인한 값을 과목별로 보여 줍니다."
    elif sources == {"submitted", "service"}:
        caption = "각 과목에 적힌 데이터 출처에서 확인한 값을 보여 줍니다."
    else:
        caption = "제출된 파일만 과목별로 셉니다. 미제출 학습은 학습 중인 기기에서 확인하세요."
    text(24, 64, caption)
    people = [(row.user, row.subjects) for row in rows]
    if not people:
        state = "unavailable" if unavailable else "no_record"
        action = "제출 기록 목록을 확인한 뒤 다시 집계하세요." if unavailable else "학습 중인 기기의 기록을 확인하세요."
        empty = tuple(analysis.SubjectSummary(key, title, state, (), analysis.NextAction("submit", "", action)) for key, title in analysis.SUBJECTS)
        people = [("학습자 목록을 확인할 수 없습니다." if unavailable else "제출된 학습 기록을 찾지 못했습니다.", empty)]
    for i, (user, subjects) in enumerate(people):
        y0 = top + i * person_height
        text(24, y0 + 23, user, 20, "#0f172a", "700")
        for j, subject in enumerate(subjects):
            x = 24 + (j % 2) * (card_width + gap)
            y = y0 + 42 + (j // 2) * (card_height + gap)
            color = COLORS[subject.status]
            out.append('<g data-subject="%s"><rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="#f8fafc" stroke="#cbd5e1"/>' % (subject.key, x, y, card_width, card_height))
            text(x + 16, y + 29, subject.title, 18, "#0f172a", "700")
            text(x + card_width - 140, y + 29, analysis.status_text(subject), 15, color, "600")
            text(x + 16, y + 50, analysis.SOURCE_LABELS[subject.source], 13, "#64748b")
            if subject.status == "unavailable":
                message = "기록이나 목록을 읽지 못해 숫자를 집계하지 않았습니다."
            elif subject.status == "no_record":
                message = "제출본에서 집계할 기록을 찾지 못했습니다."
            else:
                message = ""
                for k, metric in enumerate(subject.metrics):
                    text(x + 16, y + 76 + k * 21, analysis.metric_text(metric))
                    out.append('<title>%s</title>' % html.escape(metric.definition))
            for k, line in enumerate(_wrap(message)):
                text(x + 16, y + 78 + k * 18, line, 15, color)
            for k, line in enumerate(_wrap(subject.next_action.text)[:3]):
                text(x + 16, y + card_height - 54 + k * 18, line, 14, color)
            out.append('</g>')
    text(24, height - 16, "분모와 기록을 세는 방법은 함께 제공하는 마크다운에서 확인하세요.", 14, "#64748b")
    out.append('</svg>')
    return "\n".join(out) + "\n"


def render_markdown(rows, unavailable=False):
    return "# 과목별 학습을 확인하세요\n\n![과목별 학습 현황](dashboard.svg)\n\n" + analysis.markdown(rows, unavailable=unavailable)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=OUT_DIR)
    options = parser.parse_args()
    team = analysis.collect_team()
    rows, unavailable = team.users, team.status == "unavailable"
    study.write_text(os.path.join(options.out, "dashboard.svg"), render_svg(rows, unavailable))
    study.write_text(os.path.join(options.out, "DASHBOARD.md"), render_markdown(rows, unavailable))
    print("현황판 생성: %d명 → %s" % (len(rows), study.shown_path(options.out)))


if __name__ == "__main__":
    main()
