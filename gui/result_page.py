# -*- coding: utf-8 -*-
"""결과 화면: 점수·숙달 단원·단원별 판정·문항별 결과와 해설을 보여 줌."""
import html
import re

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import (QBoxLayout, QListWidget, QSplitter, QStyle, QStyledItemDelegate, QStyleOptionViewItem,
                             QTextBrowser, QWidget)

import mdlite
from gui import kit, motion, theme
from gui.mascot import Mascot

PARTY_RATIO = 90  # 득점률이 이 이상이면 마스코트가 웃고, 방금 제출한 회차면 색종이가 떨어짐
ROW_HEIGHT = 40  # 문항 목록 한 줄의 최소 높이. 큰 글자에서는 글자 높이를 따라 늘어남
COMPACT_ROW = 32  # 작은 창에서 목록 한 줄의 최소 높이
COMPACT_WIDTH = 944  # 이 폭보다 좁은 창에서는 여백·칸 사이·줄 높이를 줄여 표와 목록에 자리를 남김. 회차 풀이가 작은 배치로 바꾸는 폭과 같음
COMPACT_HEIGHT = 760  # 결과 화면이 이 높이보다 낮으면 폭이 넓어도 여백·칸 사이·줄 높이를 줄여 목록에 줄을 남김. 1280×800 은 넓은 배치를 유지함
COMPACT_MARGIN = 16  # 작은 창의 내용 단 여백과 카드 안 여백
TAG_BG = {"ok": "ok_weak", "wrong": "wrong_weak", "blank": "surface_alt"}  # 판정 꼬리표 바탕. 글자색은 판정 색(theme.RESULT)
TAG_TOKEN = {name: token for name, token in theme.RESULT.values()}
SPLIT_SIZES = [420, 792]  # 문항 목록 카드와 오른쪽 카드의 처음 폭


def md_html(text):
    """마크다운 문서를 다른 HTML 사이에 끼워 넣을 수 있게 body 태그를 벗김."""
    return mdlite.to_html(text)[len("<body>"):-len("</body>")]


def code_box(text):
    return ('<table width="100%%" cellspacing="0" cellpadding="8" border="0" style="margin-top:2px; margin-bottom:10px;">'
            '<tr><td class="codebox"><pre>%s</pre></td></tr></table>' % html.escape(text, quote=False))


def band(title, anchor="", space=(14, 8)):
    """구역 제목. 문제 본문 안의 제목과 섞이지 않게 띠로 만듦. space 는 띠의 (위, 아래) 여백이고 기본값은 이 화면의 문서 규칙(doc_css)에 맞춘 것임."""
    return ('<a name="%s"></a><table width="100%%" cellspacing="0" cellpadding="6" border="0" style="margin-top:%dpx; margin-bottom:%dpx;">'
            '<tr><td class="band"><b>%s</b></td></tr></table>' % (anchor, space[0], space[1], title))


def ref_html(refs, space=(14, 8)):
    """참고 자료 구역. 강의·과제 쪽수 같은 짧은 글을 한 줄로 이음. 문항에 ref 가 없으면 빈 글자를 돌려줌. space 는 band 의 여백."""
    if not refs:
        return ""
    return band("참고 자료", space=space) + "<p>%s</p>" % " · ".join(html.escape(ref, quote=False) for ref in refs)


def my_answer_html(item):
    answer = item["answer"]
    if not item["answered"]:
        return "<p>(작성하지 않았습니다)</p>"
    if item["type"] == "choice":
        picked = answer if isinstance(answer, (list, tuple)) else [answer]
        return "<p><b>%s</b></p>" % ", ".join("%s번" % n for n in picked)
    return code_box(str(answer).rstrip("\n"))


def explain_html(item, info, space=(14, 8)):
    """정답과 해설 구역. info 는 session.explain 이 돌려준 값. 오답 노트 화면도 같이 씀. space 는 band 의 여백."""
    parts = [band("정답과 해설", "answer", space)]
    if info["answer"]:
        parts.append("<p><b>정답: %s</b></p>" % info["answer"] if item["type"] == "choice"
                     else "<p><b>정답</b></p>" + code_box(info["answer"]))
    if info["markdown"]:
        parts.append(md_html(re.sub(r"^# [^\n]*\n", "", info["explain"], count=1)))  # 문서 첫 줄의 제목은 띠 제목과 겹쳐서 뺌
    else:  # 퀴즈 해설은 마크다운 문서가 아니라 한 문단짜리 글임
        parts.append("<p>%s</p>" % mdlite.inline_html(info["explain"]))
    parts.append(ref_html(item["ref"], space))
    if info["solution"]:
        parts += [band("모범 답안", space=space), code_box(info["solution"])]
    return "".join(parts)


class TagDelegate(QStyledItemDelegate):
    """문항 목록의 줄. 첫 낱말(정답·오답·미응답)을 약한 바탕의 꼬리표로 그리고 나머지 글을 그 오른쪽에 이어 그림.
    꼬리표 폭은 가장 긴 판정 이름에 맞춰 문항 번호가 한 줄로 늘어섬. 맨 위 '단원별 판정' 줄은 기본 그리기를 씀."""

    row_height = ROW_HEIGHT

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(self.row_height, size.height()))

    def paint(self, painter, option, index):
        name, _, rest = (index.data() or "").partition("  ")
        if name not in TAG_TOKEN:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        style = opt.widget.style()
        rect = QRectF(style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, opt.widget))
        opt.text = ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)  # 바탕, 고른 줄, 줄 사이 선
        tag_font = QFont(opt.font)
        tag_font.setBold(True)
        tag_metrics = QFontMetrics(tag_font)
        pad = 8
        tag_w = max(tag_metrics.horizontalAdvance(n) for n in TAG_TOKEN) + 2 * pad
        tag_h = theme.TYPE["caption"][1] + 2  # 꼬리표(QLabel#badge)와 같은 높이
        token = TAG_TOKEN[name]
        tag = QRectF(rect.left(), rect.center().y() - tag_h / 2, tag_w, tag_h)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.qcolor(TAG_BG[token]))
        painter.drawRoundedRect(tag, theme.RADIUS["dense_chip"], theme.RADIUS["dense_chip"])
        painter.setFont(tag_font)
        painter.setPen(theme.qcolor(token))
        painter.drawText(tag, Qt.AlignmentFlag.AlignCenter, name)
        text = rect.adjusted(tag_w + pad, 0, 0, 0)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)  # 고른 줄의 글자색은 스타일시트(selection_ink)를 따름
        brush = index.data(Qt.ItemDataRole.ForegroundRole)
        painter.setFont(opt.font)
        painter.setPen(theme.qcolor("selection_ink") if selected or brush is None else brush.color())
        painter.drawText(text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         opt.fontMetrics.elidedText(rest, Qt.TextElideMode.ElideRight, int(text.width())))
        painter.restore()


class VLine(QWidget):
    """폭 1px 세로선. 색은 테마의 line 이고 그릴 때마다 읽어 테마가 바뀌어도 따라감."""

    def __init__(self):
        super().__init__()
        self.setFixedWidth(1)

    def paintEvent(self, event):
        QPainter(self).fillRect(self.rect(), theme.qcolor("line"))


class ScoreRow(QWidget):
    """점수 카드의 한 줄. 왼쪽에 점수 묶음, 세로선 너머 오른쪽에 숙달 묶음을 두고 두 묶음이 폭을 반씩 나눠 선이 가운데에 옴.
    두 묶음이 한 줄에 들어가지 않으면 숙달 묶음을 점수 아래 줄로 내리고 선을 숨김."""

    def __init__(self, scores, ready):
        super().__init__()
        self.scores, self.ready = scores, ready
        self.line = VLine()
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(theme.GAP["group"])
        self.row.addWidget(scores, 1, Qt.AlignmentFlag.AlignVCenter)
        self.row.addWidget(self.line)
        self.row.addWidget(ready, 1, Qt.AlignmentFlag.AlignVCenter)

    def arrange(self):
        # 반씩 나눌 폭이 모자라도 두 묶음이 한 줄에 들어가면 쌓지 않음. 작은 창에서 점수 카드가 낮아져 목록 줄이 남음
        need = self.scores.sizeHint().width() + self.ready.minimumSizeHint().width() + 1 + 2 * theme.GAP["group"]
        stacked = self.width() < need
        direction = QBoxLayout.Direction.TopToBottom if stacked else QBoxLayout.Direction.LeftToRight
        if self.row.direction() != direction:
            self.row.setDirection(direction)
            self.row.setSpacing(theme.GAP["paragraph"] if stacked else theme.GAP["group"])
            self.row.setAlignment(self.ready, (Qt.AlignmentFlag.AlignLeft if stacked else Qt.AlignmentFlag.AlignVCenter))
            self.row.setAlignment(self.scores, (Qt.AlignmentFlag.AlignLeft if stacked else Qt.AlignmentFlag.AlignVCenter))
        self.line.setVisible(not stacked)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()


class CardHead(QWidget):
    """오른쪽 카드의 머리 줄. 제목 오른쪽에 두 단추를 두고, 작은 창에서는 제목이 카드 폭을 다 쓰게 단추를 제목 위 줄로 따로 둠.
    문항마다 제목 길이가 달라도 단추 자리가 바뀌지 않게 창 폭으로만 정함."""

    def __init__(self, title, *buttons):
        super().__init__()
        self.title = title
        self.buttons = QWidget()
        buttons_box = kit.box(self.buttons, spacing=12, horizontal=True)
        for button in buttons:
            buttons_box.addWidget(button)
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(12)
        self.row.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)
        self.row.addWidget(self.buttons, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_stacked(self, stacked):
        # 내린 단추 줄은 제목 위에 둠. 작은 창에서 떠 있는 제출 알림이 처음 화면의 단추를 가리지 않게 함
        direction = QBoxLayout.Direction.BottomToTop if stacked else QBoxLayout.Direction.LeftToRight
        if self.row.direction() != direction:
            self.row.setDirection(direction)
            self.row.setSpacing(theme.GAP["detail"] if stacked else 12)
            self.row.setAlignment(self.buttons, Qt.AlignmentFlag.AlignLeft if stacked else Qt.AlignmentFlag.AlignVCenter)


class Column(QWidget):
    """결과 화면의 내용 단. 위·아래·좌우 여백은 margin(DENSE_MARGIN, 작은 창은 COMPACT_MARGIN)이고, 창이 넓으면 홈과 같은 최대 폭(HOME_WIDTH)을
    넘는 만큼 좌우 여백을 똑같이 늘려 가운데에 둠. 제출 알림이 보일 때는 Workspace 가 바깥 상자에 알림 자리를 더함."""

    def __init__(self):
        super().__init__()
        self.margin = kit.DENSE_MARGIN
        kit.box(self, (self.margin,) * 4, theme.GAP["paragraph"])

    def place(self):
        side = self.margin + max(0, self.width() - kit.HOME_WIDTH - 2 * self.margin) // 2
        self.layout().setContentsMargins(side, self.margin, side, self.margin)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.place()


class ResultPage(QWidget):
    def __init__(self, win):
        super().__init__()
        kit.page(self)
        self.win = win
        self.view, self.verdicts, self.revealed, self.busy = None, None, set(), False

        root = kit.box(self)
        top = kit.TopBar("파이썬 스터디", dense=True)
        self.home_btn, self.title = top.back, top.title
        root.addWidget(top)
        content = kit.dense(Column())
        content_box = content.layout()
        outer = QWidget()  # 제출 알림이 보이면 이 위젯의 상자에 Workspace 가 알림 자리만큼 아래 여백을 더함
        kit.box(outer).addWidget(content)
        root.addWidget(kit.scroll(outer), 1)
        card, card_box = kit.card()
        self.content, self.score_card = content, card
        scores = QWidget()
        score_box = kit.box(scores, spacing=16, horizontal=True)
        self.mascot = Mascot(52)
        self.score = kit.label("", "display")
        self.ratio = kit.badge("", "accent")
        self.note = kit.para("", "caption", "secondary")
        ready = QWidget()
        ready_box = kit.box(ready, spacing=theme.GAP["detail"])
        self.ready_name = kit.label("숙달한 단원", "label", "secondary")
        self.ready = kit.label("", "label", bold=True)  # 숙달한 단원 수 / 전체 단원 수. 막대 오른쪽 끝에 맞춤
        ready_head = QWidget()
        ready_row = kit.box(ready_head, spacing=12, horizontal=True)
        ready_row.addWidget(self.ready_name, 0, Qt.AlignmentFlag.AlignVCenter)
        ready_row.addStretch(1)
        ready_row.addWidget(self.ready, 0, Qt.AlignmentFlag.AlignVCenter)
        self.ready_bar = kit.progress()
        self.ready_bar.setMinimumWidth(120)
        ready_box.addWidget(ready_head)
        ready_box.addWidget(self.ready_bar)
        score_box.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignVCenter)
        score_box.addWidget(self.score, 0, Qt.AlignmentFlag.AlignVCenter)
        score_box.addWidget(self.ratio, 0, Qt.AlignmentFlag.AlignVCenter)
        score_box.addStretch(1)  # 점수 묶음이 왼쪽 절반을 받아도 점수는 왼쪽에 모임
        self.score_row = ScoreRow(scores, ready)
        card_box.addWidget(self.score_row)
        card_box.addWidget(self.note)
        content_box.addWidget(card)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(20)
        list_card, list_box = kit.card(8, 0)
        self.listw = QListWidget()
        self.listw.setObjectName("plain")
        kit.typed(self.listw, "caption")
        self.listw.setMinimumWidth(260)
        self.listw.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.listw.setItemDelegate(TagDelegate(self.listw))
        list_box.addWidget(self.listw)
        right, right_box = kit.card(kit.DENSE_MARGIN, theme.GAP["title_description"])
        self.item_title = kit.ElideLabel("", "headline")
        self.explain_btn = kit.button("해설 보기", "secondary")
        self.retry_btn = kit.button("다시 풀기", "secondary")
        self.retry_btn.setToolTip("같은 회차를 열어 선택한 문항을 다시 풉니다.")
        self.head = CardHead(self.item_title, self.explain_btn, self.retry_btn)
        self.detail = QTextBrowser()
        self.detail.setObjectName("plain")
        self.detail.setOpenLinks(False)
        self.detail.document().setDocumentMargin(0)
        right_box.addWidget(self.head)
        right_box.addWidget(self.detail, 1)
        split.addWidget(list_card)
        split.addWidget(right)
        split.setStretchFactor(0, SPLIT_SIZES[0])  # 창 폭이 바뀌어도 두 카드가 처음 폭의 비율대로 늘고 줄게 함
        split.setStretchFactor(1, SPLIT_SIZES[1])
        split.setSizes(SPLIT_SIZES)
        split.setChildrenCollapsible(False)
        content_box.addWidget(split, 1)
        self.split, self.right_card, self.compact, self.narrow = split, right, None, None

        self.bar = kit.BottomBar(dense=True)
        self.status = kit.label("", "caption", "secondary")
        self.busy_bar = kit.progress()
        self.busy_bar.setRange(0, 0)
        self.busy_bar.setFixedWidth(140)
        self.busy_bar.hide()
        self.git_btn = kit.button("풀이 제출", "secondary", "m")
        self.next_btn = kit.button("", "primary", "m")
        self.bar.add_tool(self.status)
        self.bar.add_tool(self.busy_bar)
        self.bar.add_action(self.git_btn)
        self.bar.add_action(self.next_btn)
        root.addWidget(self.bar)

        self.listw.currentRowChanged.connect(self.show_row)
        self.explain_btn.clicked.connect(self.reveal)
        self.retry_btn.clicked.connect(lambda: win.open_round(self.view["id"], review=True, select=self.selected()["id"]))
        self.home_btn.clicked.connect(win.go_home)
        self.git_btn.clicked.connect(win.submit_pr)
        self.next_btn.clicked.connect(win.start_next)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()

    def arrange(self):
        """좁거나 낮은 창에서는 내용 단·카드 안 여백, 카드 사이, 목록 줄 높이를 줄임. 좁은 창에서는 두 카드 사이 폭도 줄이고
        오른쪽 카드 단추를 제목과 다른 줄에 둠."""
        narrow = self.width() < COMPACT_WIDTH
        compact = narrow or self.height() < COMPACT_HEIGHT
        if (compact, narrow) == (self.compact, self.narrow):
            return
        self.compact, self.narrow = compact, narrow
        pad = COMPACT_MARGIN if compact else kit.DENSE_MARGIN
        self.content.margin = pad
        self.content.layout().setSpacing(theme.GAP["detail"] if compact else theme.GAP["paragraph"])
        self.content.place()
        for card in (self.score_card, self.right_card):
            card.layout().setContentsMargins(pad, pad, pad, pad)
        self.split.setHandleWidth(theme.GAP["detail"] if narrow else 20)
        self.head.set_stacked(narrow)
        self.listw.itemDelegate().row_height = COMPACT_ROW if compact else ROW_HEIGHT
        self.listw.doItemsLayout()

    def load(self, rid, result=None):
        """끝난 회차의 결과를 올림. result 는 방금 채점한 결과(session.grade)이고, 없으면 기록된 결과를 보여 줌."""
        motion.clear_confetti(self)  # 앞서 본 결과에서 떨어지던 색종이가 이 결과 위에 남지 않게
        session = self.win.session
        view = session.open_round(rid)
        graded = {it["id"]: it for it in result["items"]} if result else {}
        for item in view["items"]:
            item["state"] = graded[item["id"]]["state"] if item["id"] in graded else item["result"]
            item["detail"] = graded[item["id"]]["detail"] if item["id"] in graded else None  # None 이면 이번에 채점하지 않았음
        earned = sum(item["points"] for item in view["items"] if item["state"] == "ok")
        total = sum(item["points"] for item in view["items"])
        overview = session.overview()
        self.view, self.verdicts, self.revealed = view, result["verdicts"] if result else None, set()
        self.title.setText("%s 결과" % view["title"])
        self.title.show()
        ratio = round(100 * earned / total) if total else 0
        motion.count_text(self.score, "%%d / %d점" % total, earned)
        motion.count_text(self.ratio, "득점률 %d%%", ratio)
        self.mascot.set_happy(ratio >= PARTY_RATIO)
        mastered = any(v["kind"] in ("mastered", "done") for v in self.verdicts or [])
        if result and result["completed_now"] and (ratio >= PARTY_RATIO or mastered):  # 지난 회차를 다시 열거나 다시 채점할 때는 떨어뜨리지 않음
            motion.confetti(self)
        first = view["first_score"]
        self.note.setText("첫 제출은 %s점이었습니다. 숙달 판정에는 첫 제출만 반영됩니다." % first.replace("/", " / ")
                          if first and first != "%d/%d" % (earned, total) else "")
        self.note.setVisible(bool(self.note.text()))  # 빈 안내가 점수 카드 아래에 빈 줄을 남기지 않게
        self.ready.setText("%d / %d" % (overview["mastered"], overview["total_units"]))
        self.ready_bar.setRange(0, max(1, overview["total_units"]))
        self.ready_bar.setValue(overview["mastered"])
        self.next_btn.setText(self.win.next_action(overview)[0])
        self.git_btn.setEnabled(self.win.gitflow is not None)
        self.git_btn.setToolTip(self.win.git_reason or "풀이 파일을 비공개 서버로 제출합니다.")
        self.status.setText("")
        self.listw.blockSignals(True)
        self.listw.clear()
        self.listw.addItem("단원별 판정")
        for item in view["items"]:
            name = theme.result_label(item["state"])[0]
            self.listw.addItem("%s  %d. %s · %s" % (name, item["no"], item["type_label"], item["unit_title"]))
            self.listw.item(self.listw.count() - 1).setToolTip(self.listw.item(self.listw.count() - 1).text())
        self.listw.setCurrentRow(0)
        self.listw.blockSignals(False)
        self.color_rows()
        self.show_row(0)

    def selected(self):
        """고른 문항. 맨 위의 '단원별 판정' 줄이면 None."""
        row = self.listw.currentRow()
        return self.view["items"][row - 1] if row > 0 else None

    def show_row(self, row):
        item = self.selected()
        if item is None:
            self.item_title.setText("단원별 판정")
            self.detail.setHtml(self.summary_html())
        else:
            label = "%s · %s · %d점" % (item["type_label"], item["unit_title"], item["points"])
            self.item_title.setText("%d. %s" % (item["no"], "%s · %s" % (item["title"], label) if item["kind"] == "code" else label))
            self.detail.setHtml(self.item_html(item))
        usable = item is not None and not self.busy  # 제출이 도는 중에 글자 크기나 테마가 바뀌어 다시 그려도 잠근 버튼은 켜지 않음
        self.explain_btn.setEnabled(usable and item["id"] not in self.revealed)
        self.retry_btn.setEnabled(usable and item["state"] != "ok")

    def reveal(self):
        self.revealed.add(self.selected()["id"])
        self.show_row(self.listw.currentRow())
        self.detail.scrollToAnchor("answer")  # 문제 본문이 길어도 해설이 바로 보이게

    def summary_html(self):
        count = {"ok": 0, "wrong": 0, "blank": 0}
        for item in self.view["items"]:
            count[item["state"] if item["state"] in count else "blank"] += 1
        parts = ["<p>%s</p>" % " · ".join('<span class="%s">●</span> %s %d문항' % (state, name, count[state])
                                           for state, name in (("ok", "정답"), ("wrong", "오답"), ("blank", "미응답")))]
        if self.verdicts:
            rows = "".join('<tr><td><span class="tag-verdict-%s">&nbsp;%s&nbsp;</span></td><td><span class="muted">%s</span> %s</td><td>%s</td></tr>' % (
                v["kind"], theme.VERDICT[v["kind"]][0], v["unit"], html.escape(v["title"]), self.verdict_text(v["text"]))
                for v in self.verdicts)
            parts.append('<table class="verdict" width="100%%" border="0" cellspacing="0" cellpadding="10">'
                         '<tr><th align="left">판정</th><th align="left">단원</th><th align="left">내용</th></tr>%s</table>' % rows)
        elif self.view["kind"] == "diag":
            parts.append("<p>진단 결과로 단원별 출발 레벨을 정했습니다. 단원별 상태는 홈의 단원 띠에서 볼 수 있습니다.</p>")
        else:
            parts.append("<p>단원별 판정은 제출한 직후에 보여 줍니다. 지금 단원별 상태는 홈의 단원 띠에서 볼 수 있습니다.</p>")
        parts.append('<p class="h2">문항 다시 보기</p>'
                     "<p>왼쪽에서 문항을 고르면 문제와 내 답이 나옵니다. 틀린 문항은 '다시 풀기'로 먼저 고쳐 보고, "
                     "'해설 보기'로 정답과 해설을 확인하세요.</p>")
        return "<body>%s</body>" % "".join(parts)

    @staticmethod
    def verdict_text(text):
        """판정 내용의 '→' 뒤(다음에 할 일)를 주 색으로 씀. 글은 그대로임."""
        before, arrow, after = text.partition("→")
        if not arrow:
            return html.escape(text)
        return '%s→<span style="color: %s;">%s</span>' % (html.escape(before), theme.color("link"), html.escape(after))

    def item_html(self, item):
        name, mark = theme.result_label(item["state"])
        parts = ['<p><b><span class="%s">%s</span></b></p>' % (mark, name)]
        if item["detail"]:  # 채점기가 남긴 틀린 이유(통과한 테스트 수, 처음 틀린 테스트)
            parts += [band("틀린 이유"), code_box(item["detail"])]
        elif item["detail"] is None and item["kind"] == "code" and item["state"] == "wrong":
            parts.append("<p>틀린 이유는 '다시 풀기'에서 '다시 채점'을 누르면 나옵니다.</p>")
        parts += [md_html(item["body_md"]), band("내 답"), my_answer_html(item)]
        if item["id"] in self.revealed:
            parts.append(explain_html(item, self.win.session.explain(self.view["id"], item["id"])))
        return "<body>%s</body>" % "".join(parts)

    def color_rows(self):
        """문항 줄의 글자색. 판정은 줄 앞 꼬리표가 알려서 글은 본문 색으로 씀."""
        for row, item in enumerate(self.view["items"], 1):
            self.listw.item(row).setForeground(theme.qcolor("ink"))

    def restyle(self):
        """글자 크기나 테마가 바뀌면 부름. 본문 CSS 와 목록의 결과 색을 다시 주고, 읽던 자리는 지킴."""
        self.detail.document().setDefaultStyleSheet(theme.doc_css(self.win.zoom))
        if self.view:
            self.color_rows()
            bar = self.detail.verticalScrollBar()
            place = bar.value()
            self.show_row(self.listw.currentRow())
            bar.setValue(place)

    def set_busy(self, busy, text=""):
        self.busy = busy
        for widget in (self.listw, self.explain_btn, self.retry_btn, self.home_btn, self.next_btn):
            widget.setEnabled(not busy)
        self.git_btn.setEnabled(not busy and self.win.gitflow is not None)
        self.busy_bar.setVisible(busy)
        self.status.setText(text if busy else "")
        if not busy and self.view:
            self.show_row(self.listw.currentRow())
