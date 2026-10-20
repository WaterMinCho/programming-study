"""1-3 이름 뒤집기 제한사항 검사. validate 는 solution 의 인자를 받아 어긴 줄의 문구를, 다 지키면 None 을 돌려줌."""
import re

LOWER = re.compile(r"[a-z]*\Z")


def validate(name):
    if not 1 <= len(name) <= 100000:
        return "1번 줄: name 의 길이가 %d" % len(name)
    if not LOWER.match(name):
        return "2번 줄: 소문자가 아닌 글자가 있음 %r" % name[:20]
    return None
