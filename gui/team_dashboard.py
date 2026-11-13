# -*- coding: utf-8 -*-
"""확인된 스터디원에게 수집 기록의 합계와 추이를 표시함."""
import datetime
import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QFontMetricsF, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QBoxLayout, QButtonGroup, QFrame, QPushButton, QSizePolicy, QToolTip, QWidget

from gui import kit, theme
from learning_data.collection import CollectionError

KST = datetime.timezone(datetime.timedelta(hours=9))
PERIODS = {1: "오늘", 7: "최근 7일", 15: "최근 15일", 30: "최근 30일"}

METRICS = {"opens": "문제 열기", "inputs": "입력 변경", "graded": "채점"}


def observed_total(row):
    return row["python"] + (row["ai"] or 0)


class MetricInfo(QPushButton):
    def __init__(self, title, explanation):
        super().__init__("ⓘ")
        self.setObjectName("text")
        self.setProperty("scale", "s")
        self.setAutoDefault(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(title + " 집계 기준")
        self.setToolTip(explanation)
        self.setAccessibleDescription(self.toolTip())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clicked.connect(self.show_tip)

    def show_tip(self):
        QToolTip.showText(self.mapToGlobal(self.rect().bottomLeft()), self.toolTip(), self)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if event.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason):
            self.show_tip()

    def focusOutEvent(self, event):
        QToolTip.hideText()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            QToolTip.hideText()
            event.accept()
            return
        super().keyPressEvent(event)


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

    def set_data(self, rows, days, message="", metric="graded"):
        self.rows, self.days, self.active = rows, days, None
        self.metric = metric
        empty = {"opens": "이 기간에 기록된 문제 열기가 없습니다.", "inputs": "이 기간에 기록된 입력 변경이 없습니다.",
                 "graded": "이 기간에 채점한 풀이가 없습니다."}
        if metric == "inputs" and all(row["ai"] is None for row in rows):
            empty["inputs"] = "파이썬 입력 변경이 없습니다. AI 입력은 미측정입니다."
        self.message = message or (empty[metric] if not any(map(observed_total, rows)) else "")
        self.setAccessibleName(("시간별 " if days == 1 else "일별 ") + METRICS[metric])
        self.setAccessibleDescription("\n".join(self.describe(n) for n in range(len(rows))) or self.message)
        self.update()

    def describe(self, index):
        row = self.rows[index]
        at = datetime.datetime.fromisoformat(row["at"]).astimezone(KST)
        label = "%d월 %d일" % (at.month, at.day)
        if self.days == 1:
            label += " %d시" % at.hour
        ai = "미측정" if row["ai"] is None else format(row["ai"], ",") + "건"
        if row["ai"] is not None and row.get("ai_unmeasured"):
            ai += " (미측정 기록 포함)"
        return f"{label} · 파이썬 {row['python']:,}건 · AI {ai}"

    def plot_geometry(self):
        peak = max([1] + list(map(observed_total, self.rows)))
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
            total = observed_total(row)
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
                    height = size * (row[track] or 0) / total
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
        self.metric, self.result = "graded", None
        self.setProperty("ui", "2")
        box = kit.box(self, spacing=24)
        heading = kit.heading(kit.para("스터디 수집 현황", "headline", bold=True), kit.para("파이썬과 AI 학습에서 수집한 기록을 확인합니다.", "caption", "secondary"))
        self.reload = kit.button("새로고침", "secondary")
        self.reload.clicked.connect(self.fetch)
        box.addWidget(DashboardRow([heading, self.reload], lambda: [text_width(heading.title), self.reload.sizeHint().width()], [1, 0], 16))
        self.period_title = kit.para("최근 7일 학습 활동", "title", bold=True)
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
        self.filter_row = DashboardRow([self.period_title, self.periods],
                                       lambda: [text_width(self.period_title), self.periods.sizeHint().width()], [1, 0], 16)
        box.addWidget(self.filter_row)
        definitions = {
            "cards": ("열어 본 문항", "선택 기간에 문제 열기가 기록된 서로 다른 문항 수입니다. 같은 과목의 같은 문항은 여러 사람이 여러 번 열어도 한 번만 셉니다."),
            "opens": ("문제 열기", "선택 기간에 파이썬·AI 연습과 모의고사에서 문항을 반환한 기록 수입니다. 같은 기록을 다시 보내도 한 번만 셉니다."),
            "inputs": ("입력 변경", "선택 기간에 바뀐 답을 저장한 횟수입니다. 키 입력, 같은 값 재저장, 기존 초안 다시 열기는 세지 않습니다. AI는 새 계측으로 관측한 횟수만 표시합니다."),
            "graded": ("채점", "선택 기간에 답을 쓰거나 고른 뒤 채점한 문항을 셉니다. 다시 풀고 채점하면 한 건 더 셉니다. "
                               "미응답과 [모르겠어요], 같은 기록의 재전송은 제외합니다."),
        }
        self.values, self.infos = {}, {}
        cards = []
        for key, (title, description) in definitions.items():
            card = kit.frame("team_metric")
            inner = kit.box(card, (16, 16, 16, 16), 8)
            inner.addWidget(kit.para(title, "caption", "secondary"))
            line = QWidget()
            number = kit.box(line, horizontal=True, spacing=8)
            value = kit.label("–", "headline", bold=True)
            info = MetricInfo(title, description)
            number.addWidget(value)
            number.addWidget(info)
            number.addStretch(1)
            inner.addWidget(line)
            cards.append(card)
            self.values[key], self.infos[key] = value, info

        def widths(pair):
            return [max(180, card.sizeHint().width()) for card in pair]

        pairs = [cards[:2], cards[2:]]
        halves = [DashboardRow(pair, lambda pair=pair: widths(pair), spacing=16) for pair in pairs]
        self.metrics = DashboardRow(halves, lambda: [sum(widths(pair)) + 16 for pair in pairs], spacing=16)
        box.addWidget(self.metrics)
        self.raw = kit.para("", "body", bold=True)
        box.addWidget(self.raw)
        self.identity_line = QWidget()
        secondary = kit.FlowLayout(self.identity_line, spacing=12)
        self.total, self.accounts, self.installations = [kit.label("–", "caption", "secondary") for _ in range(3)]
        self.account_period, self.device_period = [kit.label("", "caption", "secondary") for _ in range(2)]
        for name, value, detail in (("누적 채점", self.total, None), ("인증 계정", self.accounts, self.account_period),
                                    ("첫 실행 확인 기기", self.installations, self.device_period)):
            group = QWidget()
            part = kit.box(group, spacing=4, horizontal=True)
            part.addWidget(kit.label(name, "caption", "secondary"))
            part.addWidget(value)
            if detail is not None:
                part.addWidget(detail)
            secondary.addWidget(group)
        box.addWidget(self.identity_line)
        self.plot_card = kit.frame("team_plot")
        plot_box = kit.box(self.plot_card, (24, 24, 24, 24), 16)
        self.period_name = kit.para("최근 7일 채점", "caption", "secondary")
        self.period_total = kit.para("–", "headline", bold=True)
        plot_box.addWidget(kit.spaced(self.period_name, self.period_total, spacing=8))
        actions = QWidget()
        choices = kit.FlowLayout(actions, spacing=8)
        self.metric_group, self.metric_buttons = QButtonGroup(self), {}
        for metric, title in METRICS.items():
            button = kit.chip(title)
            self.metric_group.addButton(button)
            self.metric_buttons[metric] = button
            choices.addWidget(button)
            button.clicked.connect(lambda checked=False, metric=metric: self.show_metric(metric))
        plot_box.addWidget(actions)
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
        self.breakdown_title = kit.para("과목별 채점", "body", bold=True)
        breakdown.addWidget(self.breakdown_title)
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
        self.metadata = QWidget()
        facts = kit.box(self.metadata, spacing=8)
        self.metadata_heading = kit.para("", "body", bold=True)
        self.item_facts = kit.para("", "caption", "secondary")
        self.time_facts = kit.para("", "caption", "secondary")
        self.coverage = kit.para("", "caption", "secondary")
        for label in (self.metadata_heading, self.item_facts, self.time_facts, self.coverage):
            facts.addWidget(label)
        plot_box.addWidget(self.metadata)
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

    def show_metric(self, metric):
        result = self.result
        if not result or not result.get("graded") or metric not in METRICS:
            return
        if metric != "graded" and not result.get("activity"):
            return
        self.metric = metric
        self.metric_buttons[metric].setChecked(True)
        rows = result["graded"]["series"] if metric == "graded" else result["activity"][metric]
        total = sum(map(observed_total, rows))
        self.period_name.setText(PERIODS[result["days"]] + " " + METRICS[metric])
        self.period_total.setText(f"{total:,}건" if metric != "inputs" else f"관측 {total:,}건")
        self.breakdown_title.setText("과목별 " + METRICS[metric])
        for track in ("python", "ai"):
            measured = [row[track] for row in rows if row[track] is not None]
            value = sum(measured)
            count = f"{value:,}건" if measured else "미측정"
            if metric == "inputs" and track == "ai" and measured:
                count = "관측 " + count
            self.subject_totals[track].setText(count)
            self.subject_bars[track].setValue(round(100 * value / total) if total else 0)
        self.chart.set_data(rows, result["days"], metric=metric)

    def show_activity(self, result):
        activity = result.get("activity")
        self.values["graded"].setText(f"{result['graded']['period_total']:,}건")
        for key in ("cards", "opens", "inputs"):
            self.values[key].setText("–")
        self.metadata.setVisible(bool(activity))
        for name, button in self.metric_buttons.items():
            button.setEnabled(name == "graded" or bool(activity))
        graded = result["graded"]["period_total"]
        if activity:
            opens = sum(map(observed_total, activity["opens"]))
            inputs = sum(map(observed_total, activity["inputs"]))
            self.values["cards"].setText(f"{activity['distinct_cards']:,}개")
            self.values["opens"].setText(f"{opens:,}회")
            self.values["inputs"].setText(f"관측 {inputs:,}회")
            counts = activity["graded_metadata"]
            first = activity["period_first_ai_measurement_at"]
            coverage = "AI 입력은 이 기간에 미측정입니다."
            if first:
                observed = datetime.datetime.fromisoformat(first).astimezone(KST)
                coverage = f"선택 기간의 첫 AI 입력 계측 표시는 {observed:%m.%d %H:%M}입니다. 구버전의 입력 횟수는 미확인입니다."
            self.metadata_heading.setText(f"선택 기간 채점 {graded:,}건에 남은 정보")
            self.item_facts.setText(f"지문 {counts['stem']:,}건 · 개념 태그 {counts['concepts']:,}건 · "
                                    f"문항 버전 {counts['revision']:,}건 · 출제 난이도 {counts['difficulty']:,}건 "
                                    f"(미확인 {graded - counts['difficulty']:,}건)")
            python_graded = sum(row["python"] for row in result["graded"]["series"])
            self.time_facts.setText(f"순서와 기록 시각 {counts['ordered_timed']:,}건 · "
                                    f"파이썬 채점 {python_graded:,}건 중 입력 연결 {counts['linked_input']:,}건")
            self.coverage.setText(coverage)
        self.show_metric(self.metric if activity else "graded")

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
                self.result = None
                self.raw.hide()
                self.filter_row.hide()
                self.identity_line.hide()
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
            self.filter_row.show()
            self.identity_line.show()
            self.period_title.setText(PERIODS[days] + " 학습 활동")
            self.result = result
            raw_period = result.get("period_total")
            period_text = "미확인" if raw_period is None else f"{raw_period:,}건"
            self.raw.setText(f"수집 기록  누적 {result['total']:,}건 · {PERIODS[days]} {period_text}")
            self.raw.show()
            graded = result.get("graded")
            self.plot_card.setVisible(graded is not None)
            self.accounts.setText("%s개" % format(result["accounts"], ","))
            self.installations.setText("%s대" % format(result["installations"], ","))
            self.account_period.setText("(%s +%s개)" % (PERIODS[days], format(result["period_accounts"], ",")))
            self.device_period.setText("(%s +%s대)" % (PERIODS[days], format(result["period_installations"], ",")))
            kit.typed(self.note, "caption")
            self.note.line = theme.TYPE["caption"][1]
            kit.set_tone(self.note, "secondary")
            if graded is None:
                for value in self.values.values():
                    value.setText("–")
                for button in self.metric_buttons.values():
                    button.setEnabled(False)
                self.total.setText("–")
                self.note.setText("이 서버는 채점 풀이 통계를 아직 제공하지 않습니다.")
                self.show()
                return
            self.total.setText("%s건" % format(graded["total"], ","))
            self.show_activity(result)
            rows = graded["series"]
            first, last = [datetime.datetime.fromisoformat(rows[n]["at"]).astimezone(KST) for n in (0, -1)]
            dates = "%d.%d.%d" % (first.year, first.month, first.day)
            if days != 1:
                dates += " – %d.%d.%d" % (last.year, last.month, last.day)
            self.range.setText(dates + "  ·  한국 시간 · " + ("시간별 합계" if days == 1 else "일별 합계"))
            text = ""
            if not result.get("activity"):
                text = "이 서버는 문항·열기·입력 통계를 아직 제공하지 않습니다."
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
            self.note.setText(text.strip())
            self.show()
        started = self.win.run_job("수집 통계를 확인하고 있습니다.", work, done,
                                   on_fail=lambda: done({"error": "통계를 불러오지 못했습니다. 잠시 후 [새로고침]을 눌러 주세요.", "auth": False}))
        if started is False:
            self.loading = False
            for button in self.buttons.values():
                button.setEnabled(True)
            self.reload.setEnabled(True)
