# -*- coding: utf-8 -*-
"""첫 화면의 설정 단추 아래에서 화면 선택과 보조 동작을 묶어 표시함."""
from PyQt6 import sip
from PyQt6.QtCore import QEvent, QRectF, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QPainter, QPen
from PyQt6.QtWidgets import QApplication, QButtonGroup, QHBoxLayout, QWidget

from gui import feedback, kit, motion, theme


TEXT_LABELS = {"normal": "보통 글자", "large": "큰 글자", "larger": "더 큰 글자"}
THEME_LABELS = {"system": "시스템 따르기", "light": "밝게", "dark": "어둡게"}
TEXT_TIP = "화면의 글자 크기를 바꿉니다. Ctrl(맥은 Cmd)과 +, -, 0으로도 바꿀 수 있습니다."


class SettingsMenu(QWidget):
    closed = pyqtSignal()

    def __init__(self, hub, trigger):
        super().__init__(hub, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.hub, self.trigger = hub, trigger
        self.closing = False
        self.pending_action = self.focus_target = None
        self.action_timer = QTimer(self)
        self.action_timer.setSingleShot(True)
        self.action_timer.timeout.connect(self.run_action)
        self.focus_timer = QTimer(self)
        self.focus_timer.setSingleShot(True)
        self.focus_timer.timeout.connect(self.restore_focus_now)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAccessibleName("설정")
        kit.page(self)
        self.setStyleSheet('QWidget[ui="2"] QPushButton[settings_action="true"] { text-align: left; padding-left: 12px; padding-right: 12px; }')
        box = kit.box(self, (16, 16, 16, 16), theme.GAP["detail"])
        box.addWidget(kit.label("화면 설정", "headline"))
        box.addSpacing(theme.GAP["title_description"] - theme.GAP["detail"])
        box.addWidget(kit.label("글자 크기", "caption", "secondary"))
        self.text_buttons = self.choices(box, TEXT_LABELS, self.choose_text)
        for button in self.text_buttons.values():
            button.setToolTip(TEXT_TIP)
        box.addSpacing(theme.GAP["detail"])
        box.addWidget(kit.label("테마", "caption", "secondary"))
        self.theme_buttons = self.choices(box, THEME_LABELS, self.choose_theme)
        box.addSpacing(theme.GAP["paragraph"] - theme.GAP["detail"])
        self.identity_btn = self.action(box, "본인 확인 다시 하기", lambda: hub.win.ensure_identity(force=True))
        self.replay_tour = self.action(box, "첫 화면 튜토리얼 다시 보기", lambda: hub.win.show_hub_tour(replay=True))
        self.update_btn = self.action(box, "업데이트 확인", lambda: hub.win.check_updates())
        self.report_btn = self.action(box, "불편한 점 알리기", lambda: QDesktopServices.openUrl(QUrl(feedback.issue_url(hub.win))))
        self.actions = (self.identity_btn, self.replay_tour, self.update_btn, self.report_btn)
        self.anchor_timer = QTimer(self)
        self.anchor_timer.setSingleShot(True)
        self.anchor_timer.timeout.connect(self.reanchor)
        self.trigger.setCheckable(True)
        self.trigger.clicked.connect(self.toggle)
        theme.signals.changed.connect(self.restyle)
        self.hide()

    def choices(self, box, labels, choose):
        row = QHBoxLayout()
        row.setSpacing(theme.GAP["detail"])
        group = QButtonGroup(self)
        group.setExclusive(True)
        buttons = {}
        for key, text in labels.items():
            button = kit.typed(kit.button(text, "text", "s"), "caption", True)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, key=key: choose(key))
            group.addButton(button)
            row.addWidget(button)
            buttons[key] = button
        box.addLayout(row)
        return buttons

    def action(self, box, text, callback):
        button = kit.typed(kit.button(text, "text", "s"), "caption")
        button.setProperty("settings_action", True)
        button.clicked.connect(lambda: self.dismiss(after=callback))
        box.addWidget(button)
        return button

    def choose_text(self, step):
        self.hub.win.set_text(step)
        self.restyle()

    def choose_theme(self, mode):
        self.hub.win.set_theme(mode)
        self.restyle()

    def restyle(self):
        self.refresh_actions()
        for buttons, selected in ((self.text_buttons, theme.state["text"]), (self.theme_buttons, theme.state["mode"])):
            for key, button in buttons.items():
                button.setChecked(key == selected)
                button.ensurePolished()
                button.setMinimumWidth(0)
                button.setMaximumWidth(16777215)
            width = max(button.sizeHint().width() for button in buttons.values())
            for button in buttons.values():
                button.setFixedWidth(width)
        self.update()
        self.schedule_anchor()

    def refresh_actions(self, busy=False):
        win = self.hub.win
        busy = busy or win.job is not None or win.submission_running or win.pending_close or win.close_pending
        flow = win.gitflow
        self.update_btn.setEnabled(not busy and flow is not None and hasattr(flow, "updates"))
        self.identity_btn.setEnabled(not busy)
        self.replay_tour.setEnabled(not busy)
        explanation = "프로그램 파일을 바꾸지 않고 새 버전이 있는지 확인합니다."
        if busy:
            explanation += " 다른 작업이 끝난 뒤 사용할 수 있습니다."
        elif flow is None or not hasattr(flow, "updates"):
            explanation += " " + (win.git_reason or "프로그램을 다시 실행해 업데이트 기능을 준비해 주세요.")
        self.update_btn.setToolTip(explanation)

    def refont(self):
        self.restyle()

    def schedule_anchor(self):
        if self.isVisible():
            self.anchor_timer.start(0)

    def reanchor(self):
        if not self.trigger.isVisible():
            self.dismiss(immediate=True, restore_focus=False)
            return
        self.layout().activate()
        self.adjustSize()
        rect = self.trigger.rect()
        origin = self.trigger.mapToGlobal(rect.topLeft())
        anchor = self.trigger.mapToGlobal(rect.bottomRight())
        screen = QApplication.screenAt(origin) or self.trigger.screen()
        available = screen.availableGeometry()
        gap = theme.GAP["detail"]
        x = max(available.left(), min(anchor.x() + 1 - self.width(), available.right() + 1 - self.width()))
        y = anchor.y() + 1 + gap
        if y + self.height() > available.bottom() + 1:
            y = origin.y() - gap - self.height()
        y = max(available.top(), min(y, available.bottom() + 1 - self.height()))
        self.move(x, y)

    def open_menu(self, focus=True):
        QApplication.instance().installEventFilter(self)
        reversing = self.closing
        self.action_timer.stop()
        self.pending_action = None
        self.closing = False
        kit.refont(self)
        self.reanchor()
        if not self.isVisible() or reversing:
            if not self.isVisible() and hasattr(self, "_opacity_effect"):
                self._opacity_effect.setOpacity(0.0)
            self.show()
            motion.fade_opacity(self, True)
        self.trigger.setChecked(True)
        if focus:
            self.text_buttons[theme.state["text"]].setFocus(Qt.FocusReason.PopupFocusReason)

    def toggle(self):
        if self.isVisible() and not self.closing:
            self.dismiss()
        else:
            self.open_menu()

    def dismiss(self, *, after=None, immediate=False, restore_focus=True):
        if self.closing and not immediate:
            return
        self.closing = True
        self.action_timer.stop()
        self.pending_action = None

        def finish():
            self.hide()
            self.closing = False
            if restore_focus:
                self.restore_focus()
            if after is not None:
                self.pending_action = after
                self.action_timer.start(0)

        if immediate or not self.isVisible():
            motion.play(self, 0, lambda _: None, finish)
        else:
            motion.fade_opacity(self, False, finish)

    def restore_focus(self, widget=None):
        # Qt가 이전 활성 창을 복원한 뒤 초점을 돌려 즉시 지정한 초점이 덮이지 않게 함.
        self.focus_target = widget if widget is not None else self.trigger
        self.focus_timer.start(0)

    def restore_focus_now(self):
        app, widget = QApplication.instance(), self.focus_target
        self.focus_target = None
        if (widget is None or sip.isdeleted(widget) or sip.isdeleted(self.hub) or not self.hub.window().isVisible()
                or not widget.isVisible() or not widget.isEnabled()
                or app.activePopupWidget() is not None or app.activeModalWidget() is not None):
            return
        self.hub.window().activateWindow()
        widget.setFocus(Qt.FocusReason.PopupFocusReason)

    def run_action(self):
        callback, self.pending_action = self.pending_action, None
        if callback is not None and not sip.isdeleted(self.hub) and self.hub.isVisible() and self.hub.window().isVisible():
            callback()

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        self.anchor_timer.stop()
        if getattr(self, "_motion", None) is not None:
            motion.play(self, 0, lambda _: None)
        if not sip.isdeleted(self.trigger):
            self.trigger.setChecked(False)
        super().hideEvent(event)
        self.closed.emit()

    def closeEvent(self, event):
        # Popup의 자동 닫기를 종료 요청으로 전파하지 않고 페이드 뒤 숨김.
        event.ignore()
        self.dismiss()

    def controls(self):
        return [button for button in (*self.text_buttons.values(), *self.theme_buttons.values(), *self.actions)
                if button.isVisible() and button.isEnabled()]

    def focusNextPrevChild(self, forward):
        controls = self.controls()
        if not controls:
            return False
        current = QApplication.focusWidget()
        index = controls.index(current) if current in controls else -1
        controls[(index + (1 if forward else -1)) % len(controls)].setFocus(Qt.FocusReason.TabFocusReason)
        return True

    def eventFilter(self, watched, event):
        if sip.isdeleted(self.hub) or sip.isdeleted(self.trigger):
            QApplication.instance().removeEventFilter(self)
            return False
        kind = event.type()
        if watched in (self.hub, self.hub.window()) and kind in (QEvent.Type.Close, QEvent.Type.Hide):
            self.action_timer.stop()
            self.focus_timer.stop()
            self.pending_action = self.focus_target = None
            if self.isVisible():
                self.dismiss(immediate=True, restore_focus=False)
            return False
        if not self.isVisible():
            return False
        if watched in (self.trigger, self.hub, self.hub.window()) and kind in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.LayoutRequest):
            self.schedule_anchor()
        elif kind == QEvent.Type.MouseButtonPress and not self.rect().contains(self.mapFromGlobal(event.globalPosition().toPoint())):
            on_trigger = self.trigger.rect().contains(self.trigger.mapFromGlobal(event.globalPosition().toPoint()))
            self.dismiss(restore_focus=on_trigger)
            return on_trigger
        elif kind == QEvent.Type.KeyPress and isinstance(watched, QWidget) and (watched is self or self.isAncestorOf(watched)):
            # 안내의 다음·이전 단추는 안내 자체의 키 처리를 유지함.
            if watched not in self.controls() and watched is not self:
                return False
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.dismiss()
                return True
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Left, Qt.Key.Key_Right):
                forward = key in (Qt.Key.Key_Down, Qt.Key.Key_Right) or (key == Qt.Key.Key_Tab and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                return self.focusNextPrevChild(forward)
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and watched in self.controls():
                watched.click()
                return True
        return False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(theme.qcolor("surface"))
        painter.setPen(QPen(theme.qcolor("border"), 1))
        radius = theme.RADIUS["small"]
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
