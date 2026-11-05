# -*- coding: utf-8 -*-
"""학습 글에 남은 외부 강의 위치를 찾음. 검증용 메타데이터는 호출 쪽에서 제외함."""
import html
import json
import re
import unicodedata

RULE = "강의 위치 노출"
MATERIAL = r"(?:슬라이드|슬(?![가-힣])|노트북|강사\s*요약본|요약본?|대학원(?:\s*강의안)?|LectureNote|강의\s*(?:자료|노트))"
PLACE = r"(?:p\.?\s*\d+|\d+\s*(?:쪽|페이지|번?\s*셀)|(?:셀|cell)\s*\d+|\[\s*\d+\s*\])"
LOCATOR = re.compile(
    r"\d+\s*차시\s*(?:슬라이드|슬(?![가-힣])|노트북|과제|강의\s*노트|LectureNote)"
    r"|" + MATERIAL + r"\s*(?:\d+\s*(?:주차)?\s*)?(?:의\s*)?" + PLACE
    + r"|\d+\s*주차\s*(?:과제|요약본?)\s*(?:\d+\s*차시\s*)?" + PLACE,
    re.I)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})([^\s]*)\s*$")
BOX = re.compile(r"^\s*>\s*\*\*\[([^]]+)\]\*\*")
METADATA = {"ref", "facts", "where", "sources"}


def _line(text, allowed_quote=False):
    text = unicodedata.normalize("NFC", html.unescape(text))
    text = re.sub(r"[`*_]", "", text)
    parens, opened = [], []
    for n, char in enumerate(text):
        if char in "(（":
            opened.append(n)
        elif char in ")）" and opened:
            parens.append((opened.pop(), n + 1))
    parens.extend((n, len(text)) for n in opened)
    for found in LOCATOR.finditer(text):
        if allowed_quote and not any(a <= found.start() < b for a, b in parens):
            continue
        yield found.group(0)


def _json_texts(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _json_texts(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in METADATA:
                yield from _json_texts(item)


def find(text, markdown=False):
    """노출 위치를 [(줄 번호, 걸린 글)]로 돌려줌. 정정·보충 설명 인용문의 문장은 허용하고 위치 괄호는 잡음.

    마크다운의 블록 글·코드·그림 설명도 봄. ai-* JSON의 ref·facts·where·sources는 검증 기록으로 남김.
    블록 형식 검사기가 where 금지를 따로 확인함.
    """
    text = str(text or "")
    if not markdown:
        return [(n, found) for n, line in enumerate(text.splitlines(), 1) for found in _line(line)]
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    out, fence, body, start, allowed_quote = [], None, [], 0, False
    for n, line in enumerate(text.splitlines(), 1):
        mark = FENCE.match(line)
        if fence is not None:
            if mark and mark.group(1)[0] == fence[0] and len(mark.group(1)) >= len(fence) and not mark.group(2):
                if kind.startswith("ai-"):
                    try:
                        values = list(_json_texts(json.loads("\n".join(body))))
                    except ValueError:
                        values = body
                    for value in values:
                        out.extend((start, found) for part in value.splitlines() for found in _line(part))
                else:
                    out.extend((start + k, found) for k, part in enumerate(body, 1) for found in _line(part))
                fence, body = None, []
            else:
                body.append(line)
            continue
        if mark:
            fence, kind, start, allowed_quote = mark.group(1), mark.group(2), n, False
            continue
        box = BOX.match(line)
        if box:
            allowed_quote = box.group(1) in ("정정", "보충 설명")
        elif not line.lstrip().startswith(">"):
            allowed_quote = False
        out.extend((n, found) for found in _line(line, allowed_quote))
    if fence is not None:
        out.extend((start + k, found) for k, part in enumerate(body, 1) for found in _line(part))
    return out
