# -*- coding: utf-8 -*-
"""AI 비전 개론 트랙의 엔진. 화면(gui/ai_*.py)과 출제 도구(tools/ai_*.py, verify_ai.py)가 같이 씀.

bank 는 ai/ 은행 읽기(index, terms, 학습 노트, 봉인된 문항), grade 는 빈칸·고르기 채점, gen 은 숫자가 바뀌는 생성기,
review 는 카드마다의 복습 상자와 학습일, plan 은 오늘 목표와 다음 할 일, notes 는 오답 노트 갈래, service 는 AiSession 과
연습 묶음(PracticeSet)임. PyQt6 와 torch·numpy 를 import 하지 않고 표준 라이브러리만 씀.
"""
