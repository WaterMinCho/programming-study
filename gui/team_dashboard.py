# -*- coding: utf-8 -*-
"""확인된 스터디원에게 수집 기록의 합계와 추이를 표시함."""
import datetime
import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QBoxLayout, QButtonGroup, QFrame, QSizePolicy, QToolTip, QWidget

from gui import kit, theme
from learning_data.collection import CollectionError

KST = datetime.timezone(datetime.timedelta(hours=9))
PERIODS = {1: "오늘", 7: "최근 7일", 15: "최근 15일", 30: "최근 30일"}


def text_width(*labels):
    return math.ceil(max(QFontMetricsF(label.font()).horizontalAdvance(label.text()) for label in labels))


class PeriodSelector(QFrame):
    def sizeHint(self):
        layout = self.layout()
        margins = layout.contentsMargins()
        width = sum(layout.itemAt(i).sizeHint().width() for i in range(layout.count()))
        width += layout.spacing() * max(0, layout.count() - 1) + margins.left() + margins.right()
        return QSize(width, layout.heightForWidth(width))


class DashboardRow(QWidget):
    """실제 글자 폭이 부족하면 칸을 세로로 옮김."""

    def __init__(self, widgets, widths, weights=None, spacing=24):
        super().__init__()
        self.widths, self.side = widths, None
        self.row = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(spacing)
        for widget, weight in zip(widgets, weights or [1] * len(widgets)):
            self.row.addWidget(widget, weight)

    def arrange(self):
        needed = sum(self.widths()) + self.row.spacing() * (self.row.count() - 1)
        side = self.width() >= needed
        if side != self.side:
            self.side = side
            self.row.setDirection(QBoxLayout.Direction.LeftToRight if side else QBoxLayout.Direction.TopToBottom)
            self.updateGeometry()

    def refont(self):
        self.arrange()

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest:
            self.arrange()
        return result


class CollectionChart(QWidget):
    def __init__(self):
        super().__init__()
        self.rows, self.days, self.active = [], 7, None
        self.message = "통계를 불러오고 있습니다."
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.refont()

    def refont(self):
        self.setMinimumHeight(max(260, 10 * theme.TYPE["caption"][1]))
        self.updateGeometry()
        self.update()

    def set_data(self, rows, days, message=""):
        self.rows, self.days, self.active = rows, days, None
        self.message = message or ("이 기간에 채점한 풀이가 없습니다." if not any(row["python"] + row["ai"] for row in rows) else "")
        self.setAccessibleName("시간별 채점 풀이" if days == 1 else "일별 채점 풀이")
        self.setAccessibleDescription("\n".join(self.describe(n) for n in range(len(rows))) or self.message)
        self.update()

    def describe(self, index):
        row = self.rows[index]
        at = datetime.datetime.fromisoformat(row["at"]).astimezone(KST)
        label = "%d월 %d일" % (at.month, at.day)
        if self.days == 1:
            label += " %d시" % at.hour
        return "%s · 파이썬 %s건 · AI %s건 · 합계 %s건" % (label, format(row["python"], ","), format(row["ai"], ","), format(row["python"] + row["ai"], ","))

    def plot_geometry(self):
        peak = max([1] + [row["python"] + row["ai"] for row in self.rows])
        raw = max(1, peak / 4)
        power = 10 ** math.floor(math.log10(raw))
        step = next(value * power for value in (1, 2, 5, 10) if value * power >= raw)
        ceiling = math.ceil(peak / step) * step
        metrics = QFontMetricsF(theme.font("micro"))
        left = math.ceil(metrics.horizontalAdvance(format(ceiling, ","))) + 16
        line = theme.TYPE["micro"][1]
        return QRectF(left, line, max(1, self.width() - left - 8), max(1, self.height() - 3 * line - 16)), ceiling, step

    def tick_labels(self, plot):
        if not self.rows:
            return []
        labels = []
        for row in self.rows:
            at = datetime.datetime.fromisoformat(row["at"]).astimezone(KST)
            labels.append("%d시" % at.hour if self.days == 1 else "%d/%d" % (at.month, at.day))
        metrics = QFontMetricsF(theme.font("micro"))
        label_width = max(metrics.horizontalAdvance(label) for label in labels) + 16
        count = min(len(labels), max(1, min(8, int(plot.width() / label_width))))
        span = plot.width() / len(labels)
        while count:
            stride = math.ceil(len(labels) / count)
            start = 0 if self.days == 1 else (len(labels) - 1) % stride
            indices = range(start, len(labels), stride)
            ticks = [(i, labels[i], QRectF(max(plot.left(), min(plot.right() - label_width, plot.left() + span * (i + .5) - label_width / 2)),
                                          plot.bottom() + 12, label_width, theme.TYPE["micro"][1] + 4)) for i in indices]
            if all(a[2].right() + 8 <= b[2].left() for a, b in zip(ticks, ticks[1:])):
                return ticks
            count -= 1

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(theme.font("micro"))
        plot, ceiling, axis_step = self.plot_geometry()
        line = theme.TYPE["micro"][1]
        for value in range(0, ceiling + 1, axis_step):
            y = plot.bottom() - value / ceiling * plot.height()
            painter.setPen(QPen(theme.qcolor("line"), 1, Qt.PenStyle.SolidLine if value == 0 else Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(theme.qcolor("faint"))
            painter.drawText(QRectF(0, y - line, plot.left() - 12, 2 * line), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             format(value, ","))
        width = plot.width() / max(1, len(self.rows))
        bar = max(2, min(36, width * .56))
        for n, row in enumerate(self.rows):
            x = plot.left() + width * (n + .5)
            total = row["python"] + row["ai"]
            if n == self.active:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(theme.qcolor("surface_alt"))
                painter.drawRoundedRect(QRectF(x - width * .44, plot.top(), width * .88, plot.height()), 4, 4)
            if total:
                size = max(2, total / ceiling * plot.height())
                bounds = QRectF(x - bar / 2, plot.bottom() - size, bar, size)
                clip = QPainterPath()
                clip.addRoundedRect(bounds, min(5, bar / 3), min(5, bounds.height() / 2))
                painter.save()
                painter.setClipPath(clip)
                bottom = plot.bottom()
                painter.setPen(Qt.PenStyle.NoPen)
                for track, token in (("python", "series_python"), ("ai", "series_ai")):
                    height = size * row[track] / total
                    painter.setBrush(theme.qcolor(token))
                    painter.drawRect(QRectF(x - bar / 2, bottom - height, bar, height))
                    bottom -= height
                painter.restore()
        painter.setPen(theme.qcolor("faint"))
        for _, text, rect in self.tick_labels(plot):
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        if self.message:
            painter.setFont(theme.font("caption"))
            area = plot.adjusted(12, 0, -12, 0)
            flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
            text = QFontMetricsF(painter.font()).boundingRect(area, flags, self.message)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.qcolor("surface"))
            painter.drawRoundedRect(text.adjusted(-12, -8, 12, 8), 8, 8)
            painter.setPen(theme.qcolor("muted"))
            painter.drawText(area, flags, self.message)
        if self.hasFocus():
            painter.setPen(QPen(theme.qcolor("focus"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)

    def mouseMoveEvent(self, event):
        plot, _, _ = self.plot_geometry()
        if self.rows and plot.contains(event.position()):
            self.active = min(len(self.rows) - 1, int((event.position().x() - plot.left()) / plot.width() * len(self.rows)))
            QToolTip.showText(event.globalPosition().toPoint(), self.describe(self.active), self)
        else:
            self.active = None
            QToolTip.hideText()
        self.update()

    def leaveEvent(self, event):
        if not self.hasFocus():
            self.active = None
        QToolTip.hideText()
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if self.rows and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End):
            current = self.active if self.active is not None else len(self.rows) - 1
            self.active = (0 if event.key() == Qt.Key.Key_Home else len(self.rows) - 1 if event.key() == Qt.Key.Key_End
                           else max(0, min(len(self.rows) - 1, current + (1 if event.key() == Qt.Key.Key_Right else -1))))
            QToolTip.showText(self.mapToGlobal(self.rect().center()), self.describe(self.active), self)
            self.setAccessibleDescription(self.describe(self.active))
            self.update()
        else:
            super().keyPressEvent(event)


class TeamCard(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win, self.days, self.loaded, self.loading = win, 7, None, False
        self.setProperty("ui", "2")
        box = kit.box(self, spacing=24)
        heading = kit.heading(kit.para("스터디 수집 현황", "headline", bold=True), kit.para("파이썬과 AI에서 답을 쓰거나 고르고 채점한 문항을 셉니다.", "caption", "secondary"))
        self.reload = kit.button("새로고침", "secondary")
        self.reload.clicked.connect(self.fetch)
        box.addWidget(DashboardRow([heading, self.reload], lambda: [text_width(heading.title), self.reload.sizeHint().width()], [1, 0], 16))
        self.total, self.installations, self.accounts = [kit.para("–", "display", bold=True) for _ in range(3)]
        self.account_period, self.device_period = [kit.para("", "caption", "secondary") for _ in range(2)]
        metrics, metric_labels = [], []
        for name, value, detail in (("누적 채점 풀이", self.total, kit.para("정답과 오답을 모두 포함합니다.", "caption", "secondary")),
                                    ("인증 계정", self.accounts, self.account_period),
                                    ("첫 실행 확인 기기", self.installations, self.device_period)):
            metric = kit.frame("team_metric")
            layout = kit.box(metric, (24, 24, 24, 24), 8)
            label = kit.para(name, "caption", "secondary")
            layout.addWidget(label)
            layout.addWidget(value)
            layout.addWidget(detail)
            metrics.append(metric)
            metric_labels.extend((label, value, detail))
        self.metrics = DashboardRow(metrics, lambda: [max(180, text_width(*metric_labels) + 48)] * 3, spacing=16)
        box.addWidget(self.metrics)
        self.plot_card = kit.frame("team_plot")
        plot_box = kit.box(self.plot_card, (24, 24, 24, 24), 24)
        self.period_name = kit.para("최근 7일 풀이", "caption", "secondary")
        self.period_total = kit.para("–", "display", bold=True)
        period_heading = kit.spaced(self.period_name, self.period_total, spacing=8)
        self.periods = PeriodSelector()
        self.periods.setObjectName("team_periods")
        self.periods.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        row = kit.FlowLayout(self.periods, spacing=4)
        row.setContentsMargins(4, 4, 4, 4)
        self.group, self.buttons = QButtonGroup(self), {}
        for days, title in ((1, "1일"), (7, "1주"), (15, "15일"), (30, "30일")):
            button = kit.chip(title)
            button.setChecked(days == 7)
            self.group.addButton(button)
            self.buttons[days] = button
            row.addWidget(button)
            button.clicked.connect(lambda checked=False, days=days: self.select(days))
        plot_box.addWidget(DashboardRow([period_heading, self.periods], lambda: [text_width(self.period_name, self.period_total), self.periods.sizeHint().width()], [1, 0], 16))
        self.range = kit.para("", "caption", "secondary")
        plot_box.addWidget(self.range)
        chart_area = QWidget()
        area_box = kit.box(chart_area, spacing=12)
        legend = QWidget()
        legend_box = kit.FlowLayout(legend, spacing=16)
        for name, token in (("파이썬", "series_python"), ("AI 개론·응용", "series_ai")):
            item = QWidget()
            line = kit.box(item, spacing=8, horizontal=True)
            line.addWidget(kit.Dot(token))
            line.addWidget(kit.label(name, "caption", "secondary"))
            legend_box.addWidget(item)
        area_box.addWidget(legend)
        self.chart = CollectionChart()
        area_box.addWidget(self.chart)
        self.breakdown = kit.frame("team_breakdown")
        breakdown = kit.box(self.breakdown, (24, 24, 24, 24), 16)
        breakdown.addWidget(kit.para("과목별 풀이", "body", bold=True))
        self.subject_totals, self.subject_bars = {}, {}
        for key, title in (("python", "파이썬"), ("ai", "AI 개론·응용")):
            body = QWidget()
            column = kit.box(body, spacing=8)
            column.addWidget(kit.para(title, "caption", "secondary"))
            value = kit.para("–", "headline", bold=True)
            column.addWidget(value)
            bar = kit.progress()
            bar.setTextVisible(False)
            bar.setObjectName("team_" + key)
            bar.setFixedHeight(6)
            column.addWidget(bar)
            self.subject_totals[key], self.subject_bars[key] = value, bar
            breakdown.addWidget(body)
        breakdown.addStretch(1)
        self.chart_row = DashboardRow([chart_area, self.breakdown], lambda: [theme.TYPE["micro"][0] * 32, theme.TYPE["caption"][0] * 14 + 48], [3, 1])
        plot_box.addWidget(self.chart_row)
        box.addWidget(self.plot_card)
        self.note = kit.para("", "caption", "secondary")
        box.addWidget(self.note)
        self.reverify = kit.button("기기 확인 다시 하기", "text")
        self.reverify.clicked.connect(lambda: win.ensure_identity(force=True))
        box.addWidget(self.reverify, 0, Qt.AlignmentFlag.AlignLeft)
        self.reverify.hide()
        self.hide()

    def allowed(self, identity):
        try:
            return bool(identity and identity is getattr(self.win, "identity", None) and identity.settings().get("team"))
        except CollectionError:
            return False

    def refresh_identity(self):
        identity = getattr(self.win, "identity", None)
        if not self.allowed(identity):
            self.loaded = None
            self.hide()
            return
        if self.loaded is not identity and not self.loading:
            self.loading = True
            QTimer.singleShot(0, self.fetch)

    def select(self, days):
        if self.loading or self.win.job is not None:
            self.buttons[self.days].setChecked(True)
            return
        self.days = days
        self.fetch()

    def fetch(self):
        if self.win.job is not None:
            self.loading = False
            return
        identity, days = getattr(self.win, "identity", None), self.days
        if not self.allowed(identity):
            self.loading = False
            self.loaded = None
            self.hide()
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
            if not self.allowed(identity):
                self.loaded = None
                self.hide()
                self.refresh_identity()
                return
            self.loaded = identity
            if result.get("error"):
                self.metrics.hide()
                self.plot_card.hide()
                kit.typed(self.note, "body")
                self.note.line = theme.TYPE["body"][1]
                kit.set_tone(self.note, "warning")
                self.note.setText(result["error"])
                self.reverify.setVisible(result["auth"])
                self.show()
                return
            self.reverify.hide()
            self.metrics.show()
            graded = result.get("graded")
            self.plot_card.setVisible(graded is not None)
            self.accounts.setText("%s개" % format(result["accounts"], ","))
            self.installations.setText("%s대" % format(result["installations"], ","))
            self.account_period.setText("%s 첫 인증 %s개" % (PERIODS[days], format(result["period_accounts"], ",")))
            self.device_period.setText("%s 첫 실행 %s대" % (PERIODS[days], format(result["period_installations"], ",")))
            kit.typed(self.note, "caption")
            self.note.line = theme.TYPE["caption"][1]
            kit.set_tone(self.note, "secondary")
            if graded is None:
                self.total.setText("–")
                self.note.setText("이 서버는 채점 풀이 통계를 아직 제공하지 않습니다.")
                self.show()
                return
            self.total.setText("%s건" % format(graded["total"], ","))
            self.period_name.setText(PERIODS[days] + " 풀이")
            self.period_total.setText("%s건" % format(graded["period_total"], ","))
            rows = graded["series"]
            first, last = [datetime.datetime.fromisoformat(rows[n]["at"]).astimezone(KST) for n in (0, -1)]
            dates = "%d.%d.%d" % (first.year, first.month, first.day)
            if days != 1:
                dates += " – %d.%d.%d" % (last.year, last.month, last.day)
            self.range.setText(dates + "  ·  한국 시간 · " + ("시간별 합계" if days == 1 else "일별 합계"))
            for key in ("python", "ai"):
                value = sum(row[key] for row in rows)
                self.subject_totals[key].setText("%s건" % format(value, ","))
                self.subject_bars[key].setValue(round(100 * value / graded["period_total"]) if graded["period_total"] else 0)
            self.chart.set_data(rows, days)
            text = "다시 풀고 채점하면 한 건 더 셉니다. 미응답과 [모르겠어요]는 제외합니다."
            if graded["undated"]:
                text += " 시각 미확인 %s건은 누적에만 포함합니다." % format(graded["undated"], ",")
            if graded["unknown"]:
                text += " 응답 여부 미확인 %s건은 풀이 수에서 제외했습니다." % format(graded["unknown"], ",")
            try:
                at = datetime.datetime.fromisoformat(result.get("as_of", ""))
                if at.tzinfo is not None:
                    at = at.astimezone(KST)
                    text += "  %d.%d %02d:%02d 기준" % (at.month, at.day, at.hour, at.minute)
            except (TypeError, ValueError):
                pass
            self.note.setText(text)
            self.show()
        started = self.win.run_job("수집 통계를 확인하고 있습니다.", work, done,
                                   on_fail=lambda: done({"error": "통계를 불러오지 못했습니다. 잠시 후 [새로고침]을 눌러 주세요.", "auth": False}))
        if started is False:
            self.loading = False
            for button in self.buttons.values():
                button.setEnabled(True)
            self.reload.setEnabled(True)
