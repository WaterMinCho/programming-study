"""실제 공통 부품으로 화면 예시를 그려 저장함. 학습 기록과 서버에는 접근하지 않음."""
import argparse
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QWidget
from gui import kit, theme
from gui.dialog_layout import DialogLayout


def examples():
    page = QWidget()
    kit.page(page)
    layout = kit.box(page)
    top = kit.TopBar(title="공통 화면 구성")
    top.add_right(kit.button("설정", "text"))
    layout.addWidget(top)
    body = QWidget()
    content = kit.box(body, (32, 24, 32, 32), theme.GAP["group"])
    content.addWidget(kit.heading(kit.para("학습할 과정 선택하기", "title", bold=True),
                                  kit.para("메뉴와 본문, 실행 버튼을 구분합니다.", "body", "secondary")))
    tabs = kit.NavigationTabs(("개론", "응용"))
    content.addWidget(tabs)
    area, inside = kit.well(pad_x=24, pad_y=24, spacing=theme.GAP["paragraph"])
    inside.addWidget(kit.heading(kit.para("본문과 그림", "headline", bold=True),
                                 kit.para("설명과 입력은 스크롤하고, 자주 쓰는 동작은 하단에 둡니다.", "body", "secondary")))
    content.addWidget(area)
    content.addWidget(kit.para("버튼 상태", "headline", bold=True))
    controls = QWidget()
    actions = kit.FlowLayout(controls, spacing=theme.GAP["detail"])
    for title, tone, enabled in (("학습 시작", "primary", True), ("이어서 학습", "secondary", True),
                                  ("사용법", "text", True), ("채점 중", "primary", False)):
        button = kit.button(title, tone, "l")
        button.setEnabled(enabled)
        actions.addWidget(button)
    content.addWidget(controls)
    content.addStretch(1)
    layout.addWidget(kit.scroll(body), 1)
    footer = kit.BottomBar()
    footer.add_tool(kit.button("이전 문제", "text", "l"))
    footer.add_action(kit.button("나중에 계속하기", "secondary", "l"))
    footer.add_action(kit.button("답안 확인하고 채점하기", "primary", "l"))
    layout.addWidget(footer)
    dialog = QDialog(page)
    chrome = DialogLayout(dialog, "학습 기록 설정", "설정의 목적과 현재 상태를 먼저 보여줍니다.")
    chrome.content.addWidget(kit.para("공통 팝업 예시입니다. 실제 기록은 읽거나 전송하지 않습니다.", "body"))
    chrome.actions.set_actions([kit.button("동의·삭제 관리", "text")], [kit.button("닫기", "primary")])
    return page, dialog, chrome


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    theme.apply(app)
    theme.set_text("larger")
    for mode in ("light", "dark"):
        theme.set_mode(mode)
        page, dialog, chrome = examples()
        for width, height in ((1280, 800), (760, 480)):
            page.resize(width, height)
            page.show()
            kit.refont(page)
            loop = QEventLoop()
            QTimer.singleShot(100, loop.quit)
            loop.exec()
            page.grab().save(str(args.out / f"components-{mode}-{width}.png"))
        chrome.fit(640)
        dialog.show()
        app.processEvents()
        dialog.grab().save(str(args.out / f"dialog-{mode}.png"))
        dialog.close()
        page.close()
        page.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    main()
