# -*- coding: utf-8 -*-
"""확인된 스터디원에게 수집 기록의 합계만 표시함."""
import datetime
import math

from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QFontMetricsF, QPainter, QPen
from PyQt6.QtWidgets import QButtonGroup, QWidget

from gui import kit, theme
from learning_data.collection import CollectionError


class CollectionChart(QWidget):
    def __init__(self):
        super().__init__()
        self.rows, self.days = [], 7
        self.setMinimumHeight(240)

    def set_data(self, rows, days):
        self.rows, self.days = rows, days
        self.setToolTip("\n".join("%s · 파이썬 %s건 · AI %s건" % (row["at"][:16].replace("T", " "), format(row["python"], ","), format(row["ai"], ",")) for row in rows))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = theme.font("micro")
        painter.setFont(font)
        peak = max([3] + [row["python"] + row["ai"] for row in self.rows])
        metrics = QFontMetricsF(font)
        label_height = metrics.height() + 4
        left = metrics.horizontalAdvance(format(peak, ",")) + 16
        top = label_height / 2 + 4
        plot = QRectF(left, top, max(1, self.width() - left - 8), max(1, self.height() - top - label_height - 20))
        for step in range(4):
            y = plot.bottom() - step * plot.height() / 3
            painter.setPen(QPen(theme.qcolor("line"), 1))
            painter.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            painter.setPen(theme.qcolor("faint"))
            painter.drawText(QRectF(0, y - label_height / 2, left - 10, label_height), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             format(round(peak * step / 3), ","))
        width = plot.width() / max(1, len(self.rows))
        every = max(1, math.ceil(len(self.rows) / 6))
        for n, row in enumerate(self.rows):
            x = plot.left() + width * (n + 0.5)
            bottom = plot.bottom()
            bar = max(2, min(22, width - 4))
            for track, token in (("python", "series_python"), ("ai", "series_ai")):
                height = row[track] / peak * plot.height()
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(theme.qcolor(token))
                painter.drawRect(QRectF(x - bar / 2, bottom - height, bar, height))
                bottom -= height
            if n % every == 0:
                at = datetime.datetime.fromisoformat(row["at"])
                label = at.strftime("%H시") if self.days == 1 else "%d/%d" % (at.month, at.day)
                painter.setPen(theme.qcolor("faint"))
                painter.drawText(QRectF(x - 30, plot.bottom() + 12, 60, label_height), Qt.AlignmentFlag.AlignCenter, label)


class TeamCard(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win, self.days, self.loaded, self.loading = win, 7, None, False
        self.setProperty("ui", "2")
        box = kit.box(self, spacing=16)
        box.addWidget(kit.label("스터디 수집 현황", "headline", bold=True))
        box.addWidget(kit.para("파이썬과 AI 개론·응용의 수집 기록을 합산합니다.", "body", "secondary"))
        self.periods = QWidget()
        row = kit.FlowLayout(self.periods, spacing=8)
        self.group = QButtonGroup(self)
        self.buttons = {}
        for days, title in ((1, "1일"), (7, "1주"), (15, "15일"), (30, "30일")):
            button = kit.chip(title)
            button.setChecked(days == 7)
            self.group.addButton(button)
            self.buttons[days] = button
            row.addWidget(button)
            button.clicked.connect(lambda checked=False, days=days: self.select(days))
        box.addWidget(self.periods)
        self.total = kit.para("", "title", bold=True)
        self.period_total = kit.para("", "body", "secondary")
        self.installations = kit.para("", "body", "secondary")
        self.accounts = kit.para("", "body", "secondary")
        box.addWidget(self.total)
        box.addWidget(self.period_total)
        box.addWidget(self.installations)
        box.addWidget(self.accounts)
        box.addWidget(kit.para("파이썬은 초록색, AI는 주황색 막대입니다.", "caption", "secondary"))
        self.chart = CollectionChart()
        box.addWidget(self.chart)
        self.note = kit.para("", "caption", "secondary")
        box.addWidget(self.note)
        self.reload = kit.button("통계 새로고침", "text")
        self.reload.clicked.connect(self.fetch)
        box.addWidget(self.reload, 0, Qt.AlignmentFlag.AlignLeft)
        self.reverify = kit.button("기기 확인 다시 하기", "text")
        self.reverify.clicked.connect(lambda: win.ensure_identity(force=True))
        box.addWidget(self.reverify, 0, Qt.AlignmentFlag.AlignLeft)
        self.reverify.hide()
        self.hide()

    def refresh_identity(self):
        identity = getattr(self.win, "identity", None)
        try:
            allowed = bool(identity and identity.settings().get("team"))
        except CollectionError:
            allowed = False
        if not allowed:
            self.hide()
            return
        if self.loaded is not identity and not self.loading:
            self.loading = True
            QTimer.singleShot(0, self.fetch)

    def select(self, days):
        if self.win.job is not None:
            self.buttons[self.days].setChecked(True)
            return
        self.days = days
        self.fetch()

    def fetch(self):
        if self.win.job is not None:
            self.loading = False
            return
        identity, days = getattr(self.win, "identity", None), self.days
        if identity is None:
            return
        self.loading = True
        for button in self.buttons.values():
            button.setEnabled(False)
        self.reload.setEnabled(False)
        def work():
            try:
                return identity.summary(days)
            except CollectionError as failure:
                return {"error": str(failure), "auth": failure.status in (401, 403)}
        def done(result):
            self.loading = False
            for button in self.buttons.values():
                button.setEnabled(True)
            self.reload.setEnabled(True)
            self.loaded = identity
            if identity is not getattr(self.win, "identity", None):
                return
            if result.get("error"):
                for label in (self.total, self.period_total, self.installations, self.accounts):
                    label.clear()
                self.chart.set_data([], days)
                self.note.setText(result["error"])
                self.reverify.setVisible(result["auth"])
                self.show()
                return
            self.reverify.hide()
            self.total.setText("전체 수집 기록 %s건" % format(result["total"], ","))
            self.period_total.setText("선택한 기간 %s건" % format(result["period_total"], ","))
            self.installations.setText("첫 실행 확인 기기 %s대 · 선택 기간 %s대" % (format(result.get("installations", 0), ","), format(result.get("period_installations", 0), ",")))
            self.accounts.setText("인증 계정 %s개 · 선택 기간 첫 인증 %s개" % (format(result["accounts"], ","), format(result["period_accounts"], ",")))
            self.chart.set_data(result["series"], days)
            text = "기록에 저장된 시각을 한국 시간으로 집계합니다. 재전송은 중복 합산하지 않고 합성 기록은 제외합니다."
            if result["undated"]:
                text += " 시각 미확인 %s건은 전체 합계에만 포함합니다." % format(result["undated"], ",")
            self.note.setText(text)
            self.show()
        self.win.run_job("수집 통계를 확인하고 있습니다.", work, done)
