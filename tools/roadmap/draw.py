#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""README 학습 로드맵 그림을 그림.

같은 폴더의 roadmap.json 을 읽어 docs/roadmap/intro.png 와 길마다 한 장(arm.png 처럼 길 id 를 파일 이름으로)을 만듦.
저장소 맨 위에서 `python tools/roadmap/draw.py` 로 실행함. Pillow 가 필요함(`pip install pillow`).
글꼴은 gui/fonts 의 나눔고딕을 씀. 네 배로 그린 뒤 두 배로 줄여 저장해서 선과 원의 가장자리가 매끄러움.
"""
import json
import math
import os
import re

from PIL import Image, ImageColor, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FONT_DIR = os.path.join(ROOT, "gui", "fonts")
OUT_DIR = os.path.join(ROOT, "docs", "roadmap")

W = 1200  # 그림 너비. 아래 좌표와 크기는 모두 이 단위임
SS = 4  # 그릴 때 배율
OUT = 2  # 저장 배율
MARGIN = 30
INK = "#212529"
MUTED = "#495057"
PANEL = "#F8F9FA"  # 첫 그림의 묶음 상자 바탕

# 길 그림의 배치
CENTER = 600
MAIN_SHIFT = 36  # 노란 상자를 좌우로 번갈아 비켜 놓는 거리
LEFT_IN = 340  # 왼쪽 하위 상자의 오른쪽 끝
RIGHT_IN = 860  # 오른쪽 하위 상자의 왼쪽 끝
SUB_MIN, SUB_MAX = 200, 290
MAIN_MIN, MAIN_MAX = 210, 320
SUB_H, MAIN_H = 36, 46
STACK_GAP = 12
ROW_GAP = 34
NOTE_W = 310

BADGE_R = 10
VERIFY_ROOM = 36  # 물음표 표시가 붙은 상자에서 가운데 글의 양옆에 비워 둘 너비
TAG_H, TAG_GAP = 20, 8
TAG_SIZE = 12

_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        name = "NanumGothic-Bold.ttf" if bold else "NanumGothic-Regular.ttf"
        _fonts[key] = ImageFont.truetype(os.path.join(FONT_DIR, name), round(size * SS))
    return _fonts[key]


def tw(text, size, bold=False):
    return font(size, bold).getlength(text) / SS


def tag_w(tag):
    return tw(tag, TAG_SIZE, True) + 14


def wrap(text, size, bold, width):
    """띄어쓰기 단위로 줄을 나눔. 한 덩어리가 한 줄보다 길면 글자 단위로 자름."""
    lines, cur = [], ""
    for word in text.split(" "):
        cand = word if not cur else cur + " " + word
        if tw(cand, size, bold) <= width:
            cur = cand
            continue
        if cur:
            lines.append(cur)
        while tw(word, size, bold) > width:
            k = len(word) - 1
            while k > 1 and tw(word[:k], size, bold) > width:
                k -= 1
            lines.append(word[:k])
            word = word[k:]
        cur = word
    if cur:
        lines.append(cur)
    return lines


class Row:
    """상자 안의 글 한 줄. 꼬리표(트랙 이름)를 줄 끝에 붙일 수 있음."""

    def __init__(self, text, size, bold=False, color=INK, tag=None):
        self.text, self.size, self.bold, self.color, self.tag = text, size, bold, color, tag

    @property
    def width(self):
        w = tw(self.text, self.size, self.bold) if self.text else 0
        if self.tag:
            w += (TAG_GAP if self.text else 0) + tag_w(self.tag)
        return w

    @property
    def height(self):
        h = self.size * 1.45 if self.text else 0
        return max(h, TAG_H + 4) if self.tag else h


def balanced_width(text, size, bold, width):
    """줄 수는 그대로 두고 줄 길이가 고르게 되는 가장 좁은 너비. 마지막 줄에 한 낱말만 남을 때 씀."""
    n = len(wrap(text, size, bold, width))
    lo, hi = width / 2, width
    while hi - lo > 1:
        mid = (lo + hi) / 2
        if len(wrap(text, size, bold, mid)) == n:
            hi = mid
        else:
            lo = mid
    return hi


def rows_for(text, size, bold, color, width, tag=None):
    rows = [Row(s, size, bold, color) for s in wrap(text, size, bold, width)]
    if tag:
        if rows[-1].width + TAG_GAP + tag_w(tag) <= width:
            rows[-1].tag = tag
        else:
            rows.append(Row("", size, bold, color, tag))
    return rows


def natural_w(text, size, bold, tag=None):
    return tw(text, size, bold) + (TAG_GAP + tag_w(tag) if tag else 0)


class Box:
    def __init__(self, x, y, w, h, rows, fill, status=None, verify=False, corner="left",
                 shadow=True, align="center", pad=14):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.rows, self.fill, self.status, self.verify = rows, fill, status, verify
        self.corner, self.shadow, self.align, self.pad = corner, shadow, align, pad

    @property
    def x1(self):
        return self.x + self.w

    @property
    def y1(self):
        return self.y + self.h

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def content_h(self):
        return sum(r.height for r in self.rows)


class Canvas:
    def __init__(self, height, keep):
        self.height = math.ceil(height)
        self.keep = keep
        self.im = Image.new("RGB", (W * SS, self.height * SS), "white")
        self.d = ImageDraw.Draw(self.im)

    def rect(self, x, y, w, h, fill=None, outline=None, width=0, radius=0):
        box = [x * SS, y * SS, (x + w) * SS, (y + h) * SS]
        if radius:
            self.d.rounded_rectangle(box, radius * SS, fill=fill, outline=outline, width=round(width * SS))
        else:
            self.d.rectangle(box, fill=fill, outline=outline, width=round(width * SS))

    def circle(self, cx, cy, r, fill=None, outline=None, width=0):
        self.d.ellipse([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS],
                       fill=fill, outline=outline, width=round(width * SS))

    def line(self, pts, color, width):
        self.d.line([(x * SS, y * SS) for x, y in pts], fill=color, width=round(width * SS), joint="curve")
        for x, y in (pts[0], pts[-1]):
            self.circle(x, y, width / 2, fill=color)

    def dotted(self, a, b, color, step=7, r=1.7):
        n = max(1, round(math.dist(a, b) / step))
        for i in range(n + 1):
            t = i / n
            self.circle(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, r, fill=color)

    def text(self, x, y, s, size, bold=False, color=INK, anchor="lm"):
        self.d.text((x * SS, y * SS), s, font=font(size, bold), fill=color, anchor=anchor)

    def save(self, path):
        """256색 팔레트로 줄여 1 MB 아래로 저장함. 배지와 상자 색(keep)은 팔레트에 그대로 넣어 색이 바뀌지 않게 함."""
        im = self.im.resize((W * OUT, self.height * OUT), Image.LANCZOS)
        keep = sorted({ImageColor.getrgb(c) for c in self.keep})
        rest = 256 - len(keep)
        pal = im.quantize(colors=rest, method=Image.Quantize.FASTOCTREE).getpalette()[:rest * 3]
        pal += [v for c in keep for v in c]
        pimg = Image.new("P", (1, 1))
        pimg.putpalette(pal + [0] * (768 - len(pal)))
        im.quantize(palette=pimg, dither=Image.Dither.NONE).save(path, optimize=True)


def bezier(p0, p1, p2, p3, n=60):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def arrow(cv, pts, color, width, head=12):
    tip = pts[-1]
    back = next((p for p in reversed(pts) if math.dist(p, tip) >= head), pts[0])
    ang = math.atan2(tip[1] - back[1], tip[0] - back[0])
    ux, uy = math.cos(ang), math.sin(ang)
    base = (tip[0] - ux * head, tip[1] - uy * head)
    # 선 끝이 화살촉 밖으로 삐져나오지 않게 화살촉 밑변에서 끊음
    body = [p for p in pts if math.dist(p, tip) > head * 0.8] + [base]
    cv.line(body, color, width)
    half = head * 0.55
    tri = [tip, (base[0] - uy * half, base[1] + ux * half), (base[0] + uy * half, base[1] - ux * half)]
    cv.d.polygon([(x * SS, y * SS) for x, y in tri], fill=color)


def draw_tag(cv, x, cy, tag, st):
    w = tag_w(tag)
    cv.rect(x, cy - TAG_H / 2, w, TAG_H, fill=st["track_tag_fill"], radius=TAG_H / 2)
    cv.text(x + w / 2, cy + 0.5, tag, TAG_SIZE, True, st["track_tag_text"], "mm")


def draw_badge(cv, cx, cy, color):
    cv.circle(cx, cy, BADGE_R, fill=color, outline="white", width=1.5)
    cv.line([(cx - 4.6, cy + 0.2), (cx - 1.5, cy + 3.4), (cx + 4.8, cy - 3.8)], "white", 2.3)


def draw_verify(cv, cx, cy, text):
    cv.circle(cx, cy, 8, fill="white", outline=INK, width=1.6)
    cv.text(cx, cy + 0.5, text, 11, True, INK, "mm")


def draw_box(cv, b, data):
    st = data["style"]
    colors = {item["status"]: item["color"] for item in data["legend"]}
    if b.shadow:
        cv.rect(b.x + 2.5, b.y + 2.5, b.w, b.h, fill=st["border"])
    cv.rect(b.x, b.y, b.w, b.h, fill=b.fill, outline=st["border"], width=2)
    y = b.y + (b.h - b.content_h()) / 2
    for r in b.rows:
        x = b.x + (b.w - r.width) / 2 if b.align == "center" else b.x + b.pad
        cy = y + r.height / 2
        if r.text:
            cv.text(x, cy, r.text, r.size, r.bold, r.color)
            x += tw(r.text, r.size, r.bold) + TAG_GAP
        if r.tag:
            draw_tag(cv, x, cy, r.tag, st)
        y += r.height
    if b.status:
        bx = b.x + 3 if b.corner == "left" else b.x1 - 3
        draw_badge(cv, bx, b.y + 3, colors[b.status])
        if b.verify:
            vx = bx + 23 if b.corner == "left" else bx - 23
            draw_verify(cv, vx, b.y + 3, data["verify_mark"]["text"])


def check_layout(name, boxes):
    """글이 상자 밖으로 나가거나 상자끼리 겹치면 멈춤."""
    for b in boxes:
        for r in b.rows:
            if r.width > b.w - 2 * min(b.pad, 8) + 0.5:
                raise ValueError("%s: 글이 상자보다 넓음: %r" % (name, r.text or r.tag))
        if b.content_h() > b.h + 0.5:
            raise ValueError("%s: 글이 상자보다 높음: %r" % (name, b.rows[0].text))
        if b.verify and (b.w - b.rows[0].width) / 2 < VERIFY_ROOM - 0.5:
            raise ValueError("%s: 글이 물음표 표시에 닿음: %r" % (name, b.rows[0].text))
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if a.x < b.x1 and b.x < a.x1 and a.y < b.y1 and b.y < a.y1:
                raise ValueError("%s: 상자가 겹침: %r, %r" % (name, a.rows[0].text, b.rows[0].text))


def legend(data, verify_used, tracks):
    """범례 상자. (너비, 높이, 그리기 함수)를 돌려줌."""
    items = [(item["color"], item["label"]) for item in data["legend"]]
    if verify_used:
        items.append((None, data["verify_mark"]["label"]))
    row_h, pad = 26, 16
    w = max(tw(label, 14) for _, label in items) + 2 * pad + 28
    h = pad + len(items) * row_h
    if tracks:
        w = max(w, tw(data["track_legend"], 13) + 2 * pad, sum(tag_w(t) + 6 for t in tracks) - 6 + 2 * pad)
        h += 8 + 20 + TAG_H + 4
    h += pad - 4

    def draw(cv, x, y, box_h=None):
        cv.rect(x, y, w, box_h or h, fill="white", outline=INK, width=2)
        cy = y + pad + row_h / 2 - 2
        for color, label in items:
            if color:
                draw_badge(cv, x + pad + 10, cy, color)
            else:
                draw_verify(cv, x + pad + 10, cy, data["verify_mark"]["text"])
            cv.text(x + pad + 28, cy, label, 14)
            cy += row_h
        if tracks:
            cy += 8
            cv.text(x + pad, cy, data["track_legend"], 13, False, MUTED)
            tx, cy = x + pad, cy + 20 + 2
            for t in tracks:
                draw_tag(cv, tx, cy, t, data["style"])
                tx += tag_w(t) + 6

    return w, h, draw


def key_colors(data):
    return [item["color"] for item in data["legend"]] + list(data["style"].values()) + ["#FFFFFF", INK, MUTED]


def used_tracks(data, items):
    found = {i.get("track") for i in items}
    return [t for t in data["tracks"] if t in found]


# 길 그림


def path_page(data, p):
    st = data["style"]
    nodes = p["nodes"]
    subs = [s for n in nodes for s in n.get("left", []) + n.get("right", [])]
    everything = nodes + subs
    verify_used = any(i.get("verify") for i in everything)
    lw, lh, draw_legend = legend(data, verify_used, used_tracks(data, everything))

    basis = re.match(r"^(.*?) 공고", data["postings_basis"]).group(1)
    po = p["postings"]
    info_rows = [Row("채용 공고 %d건" % po["count"], 16, True),
                 Row("%d개사, 신입 가능 %d건" % (po["companies"], po["entry"]), 14),
                 Row("%s 기준" % basis, 13, False, MUTED)]
    info_w = max(r.width for r in info_rows) + 36
    info = Box(W - MARGIN - info_w, 20, info_w, sum(r.height for r in info_rows) + 30, info_rows, "white",
               shadow=False)

    # 제목은 범례와 공고 상자 사이에 들어가는 크기로 씀
    room = 2 * min(CENTER - (MARGIN + lw + 20), info.x - 20 - CENTER)
    size = 34
    while size > 22 and tw(p["title"], size, True) > room:
        size -= 2
    title_y = 70
    sub_y = title_y + size / 2 + 22
    spine_top = sub_y + 30

    # 하위 상자 너비는 길 안에서 하나로 맞춤
    sub_w = max(SUB_MIN, min(SUB_MAX, max(natural_w(s["label"], 15, False, s.get("track"))
                                          + (2 * VERIFY_ROOM if s.get("verify") else 30) for s in subs)))

    boxes, lines, mains = [info], [], []
    notes = {}
    for note in p.get("notes", []):
        notes.setdefault(note["near"], []).append(note)
    y = max(20 + lh, info.y1, spine_top) + 46
    for i, n in enumerate(nodes):
        cx = CENTER + (MAIN_SHIFT if i % 2 else -MAIN_SHIFT)
        mw = max(MAIN_MIN, min(MAIN_MAX, natural_w(n["label"], 17, True, n.get("track"))
                               + (2 * VERIFY_ROOM if n.get("verify") else 40)))
        mrows = rows_for(n["label"], 17, True, INK, mw - 36, n.get("track"))
        mh = max(MAIN_H, sum(r.height for r in mrows) + 18)

        side = {}
        for key in ("left", "right"):
            stack = []
            for s in n.get(key, []):
                rows = rows_for(s["label"], 15, False, INK, sub_w - 28, s.get("track"))
                fill = st["alt_fill"] if s["status"] == "alt" else st["sub_fill"]
                stack.append(Box(0, 0, sub_w, max(SUB_H, sum(r.height for r in rows) + 12), rows, fill,
                                 s["status"], s.get("verify"), key))
            side[key] = stack
        stack_h = {k: sum(b.h for b in v) + STACK_GAP * max(0, len(v) - 1) for k, v in side.items()}
        core = max(mh, stack_h["left"], stack_h["right"])
        mid = y + core / 2
        main = Box(cx - mw / 2, mid - mh / 2, mw, mh, mrows, st["main_fill"], n["status"], n.get("verify"))
        mains.append(main)
        bottom = y + core
        for key, stack in side.items():
            sy = mid - stack_h[key] / 2
            for b in stack:
                b.x = LEFT_IN - sub_w if key == "left" else RIGHT_IN
                b.y = sy
                sy += b.h + STACK_GAP
                # 점선은 노란 상자의 옆면으로 모임. 왼쪽 위 귀퉁이에는 배지가 있어 그 아래로 받음
                top = main.y + (BADGE_R + 8 if key == "left" else 10)
                ey = min(max(b.cy, top), main.y1 - 10)
                if key == "left":
                    lines.append(((b.x1, b.cy), (main.x, ey)))
                else:
                    lines.append(((b.x, b.cy), (main.x1, ey)))
            boxes.extend(stack)
        # 글상자는 하위 상자 묶음이 짧은 쪽 아래에 둠
        side_bottom = {k: mid + stack_h[k] / 2 for k in side}
        for note in notes.get(n["id"], []):
            key = "left" if side_bottom["left"] <= side_bottom["right"] else "right"
            # 글에 \n 을 넣었으면 그 자리에서 줄을 나눔
            rows = []
            for part in note["text"].split("\n"):
                width = NOTE_W - 28
                wrapped = wrap(part, 14, False, width)
                if len(wrapped) > 1 and " " not in wrapped[-1]:
                    width = balanced_width(part, 14, False, width)
                rows += rows_for(part, 14, False, INK, width)
            nh = sum(r.height for r in rows) + 22
            nx = LEFT_IN - NOTE_W if key == "left" else RIGHT_IN
            nb = Box(nx, side_bottom[key] + 16, NOTE_W, nh, rows, "white", shadow=False, align="left")
            boxes.append(nb)
            side_bottom[key] = nb.y1
            bottom = max(bottom, nb.y1)
        boxes.append(main)
        y = bottom + ROW_GAP

    height = y - ROW_GAP + 40
    check_layout(p["id"], boxes)

    cv = Canvas(height, key_colors(data))
    spine = [(CENTER, spine_top)] + [(m.cx, m.cy) for m in mains]
    for k in range(len(spine) - 1):
        a, b = spine[k], spine[k + 1]
        bend = 46 if k % 2 else -46
        dy = b[1] - a[1]
        pts = bezier(a, (a[0] + bend, a[1] + dy * 0.5), (b[0] + bend, b[1] - dy * 0.5), b)
        cv.line(pts, st["spine"], 4)
    for a, b in lines:
        cv.dotted(a, b, st["dots"])
    for b in boxes:
        draw_box(cv, b, data)
    draw_legend(cv, MARGIN, 20)
    cv.text(CENTER, title_y, p["title"], size, True, INK, "mm")
    cv.text(CENTER, sub_y, p["subtitle"], 17, False, MUTED, "mm")
    return cv


# 첫 그림


def edge_point(b, toward):
    """상자 가운데에서 toward 쪽으로 그은 선이 테두리와 만나는 점."""
    dx, dy = toward[0] - b.cx, toward[1] - b.cy
    t = min(b.w / 2 / abs(dx) if dx else math.inf, b.h / 2 / abs(dy) if dy else math.inf)
    return b.cx + dx * t, b.cy + dy * t


def segment_hits(a, b, box):
    for i in range(41):
        t = i / 40
        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        if box.x < x < box.x1 and box.y < y < box.y1:
            return True
    return False


def draw_label(cv, x, y, text, color, fill):
    w = tw(text, 12, True) + 10
    cv.rect(x - w / 2, y - 10, w, 20, fill=fill, radius=4)
    cv.text(x, y, text, 12, True, color, "mm")


def intro_page(data):
    st = data["style"]
    it = data["intro"]
    paths = {p["id"]: p for p in data["paths"]}

    # 왼쪽 줄: 모든 길에 필요한 것
    col_w = 270
    boxes = []
    y = 56
    for c in data["common"]:
        rows = rows_for(c["label"], 15, True, INK, col_w - 28, c.get("track"))
        rows += rows_for(c["evidence"], 13, False, MUTED, col_w - 28)
        h = sum(r.height for r in rows) + 18
        boxes.append(Box(MARGIN, y, col_w, h, rows, st["main_fill"], c["status"], c.get("verify")))
        y += h + 14
    _, lh, draw_legend = legend(data, any(c.get("verify") for c in data["common"]),
                                 used_tracks(data, data["common"]))
    legend_y = y + 14

    # 오른쪽: 제목, 질문, 묶음, 과정 순서
    area_x = MARGIN + col_w + 30
    cx = (area_x + W - MARGIN) / 2
    title_y, cap_y = 46, 92
    bar = (118, 166)
    q_y = 186

    box_w, col_gap, pad, head = 210, 60, 20, 44
    groups = []
    gx = area_x
    for g in it["groups"]:
        cols = 2 if len(g["paths"]) > 2 else 1
        gw = cols * box_w + (cols - 1) * col_gap + 2 * pad
        groups.append({"label": g["label"], "paths": g["paths"], "cols": cols, "x": gx, "w": gw})
        gx += gw + 70
    if gx - 70 > W - MARGIN:
        raise ValueError("intro: 묶음이 그림 너비를 넘음")
    # 남는 너비는 묶음 사이에 나눠 둠
    spare = W - MARGIN - (gx - 70)
    for k, g in enumerate(groups):
        g["x"] += spare * k / (len(groups) - 1) if len(groups) > 1 else spare / 2

    path_rows = {}
    for pid in it["paths"]:
        p = paths[pid]
        rows = rows_for(p["title"], 16, True, INK, box_w - 24)
        rows += rows_for(p["subtitle"], 13, False, MUTED, box_w - 24)
        rows.append(Row("공고 %d건, 신입 가능 %d건" % (p["postings"]["count"], p["postings"]["entry"]), 13, False, MUTED))
        path_rows[pid] = rows
    box_h = max(sum(r.height for r in rows) for rows in path_rows.values()) + 20
    row_gap = 84
    panel_top = q_y + 100
    pboxes = {}
    max_rows = max(math.ceil(len(g["paths"]) / g["cols"]) for g in groups)
    for g in groups:
        for k, pid in enumerate(g["paths"]):
            col, row = k % g["cols"], k // g["cols"]
            # 칸이 모자란 묶음은 아래 줄부터 채워서 다른 묶음의 아래 줄과 높이를 맞춤
            row += max_rows - math.ceil(len(g["paths"]) / g["cols"])
            bx = g["x"] + pad + col * (box_w + col_gap)
            by = panel_top + head + row * (box_h + row_gap)
            pboxes[pid] = Box(bx, by, box_w, box_h, path_rows[pid], st["sub_fill"])
    rows_bottom = panel_top + head + max_rows * box_h + (max_rows - 1) * row_gap
    panel_bottom = rows_bottom + 64

    # 길 사이 화살표. 곧게 그으면 다른 상자를 지나는 것은 상자 아래로 돌림
    links = []
    for ln in it["links"]:
        a, b = pboxes[ln["from"]], pboxes[ln["to"]]
        others = [o for o in pboxes.values() if o is not a and o is not b]
        p0, p1 = edge_point(a, (b.cx, b.cy)), edge_point(b, (a.cx, a.cy))
        if abs(a.cx - b.cx) < 1:
            p0, p1 = (a.cx, a.y if b.cy < a.cy else a.y1), (b.cx, b.y1 if b.cy < a.cy else b.y)
        if any(segment_hits(p0, p1, o) for o in others):
            low = max(a.y1, b.y1) + 44
            pts = bezier((a.cx, a.y1), (a.cx, low), (b.cx, low), (b.cx, b.y1))
            mid = pts[len(pts) // 2]
        else:
            pts = [p0, p1]
            mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
            if abs(p0[1] - p1[1]) < 1:
                mid = (mid[0], mid[1] - 14)
        links.append((pts, mid, ln["label"]))

    # 과정 순서 띠
    side = it["side"]
    tl_top = panel_bottom + 30
    tl_x, tl_w = area_x, W - MARGIN - area_x
    step = (tl_w - 32) / len(side["items"])
    tl_names = [rows_for(item["label"], 13, True, INK, step - 10) for item in side["items"]]
    name_h = max(sum(r.height for r in rows) for rows in tl_names)
    tl_info = [[Row("%d시간" % item["hours"], 13), Row(item["when"], 13, False, MUTED)] for item in side["items"]]
    info_h = max(sum(r.height for r in rows) for rows in tl_info)
    tl_need = 16 + 22 + 18 + 14 + name_h + 4 + info_h + 14
    tl_top = legend_y = max(tl_top, legend_y)
    tl_h = max(tl_need, lh)
    height = tl_top + tl_h + 30

    all_boxes = boxes + list(pboxes.values())
    check_layout("intro", all_boxes)
    cv = Canvas(height, key_colors(data))

    # 왼쪽 줄
    cv.text(MARGIN, 32, it["common_title"], 17, True)
    for b in boxes:
        draw_box(cv, b, data)
    draw_legend(cv, MARGIN, legend_y, tl_h)

    # 제목과 질문
    cv.text(cx, title_y, it["title"], 34, True, INK, "mm")
    cv.text(cx, cap_y, it["caption"], 15, False, MUTED, "mm")
    cv.line([(cx, bar[0]), (cx, bar[1])], MUTED, 4)
    cv.text(cx, q_y, it["question"], 19, False, INK, "mm")

    # 묶음 상자와 질문에서 내려가는 화살표
    for g in groups:
        gx, gw = g["x"], g["w"]
        cv.rect(gx, panel_top, gw, panel_bottom - panel_top, fill=PANEL, outline="#ADB5BD", width=1.5, radius=10)
        cv.text(gx + gw / 2, panel_top + 24, g["label"], 15, True, INK, "mm")
        sx = cx + (-40 if gx + gw / 2 < cx else 40)
        ex, ey = gx + gw / 2, panel_top - 6
        sy = q_y + 20
        pts = bezier((sx, sy), (sx + (ex - sx) * 0.15, sy + (ey - sy) * 0.8), (ex, sy + (ey - sy) * 0.15), (ex, ey))
        arrow(cv, pts, st["spine"], 4, 14)
    for pts, mid, label in links:
        arrow(cv, pts, st["spine"], 2.5, 11)
    for b in pboxes.values():
        draw_box(cv, b, data)
    for pts, mid, label in links:
        inside = any(g["x"] < mid[0] < g["x"] + g["w"] and panel_top < mid[1] < panel_bottom for g in groups)
        draw_label(cv, mid[0], mid[1], label, st["track_tag_text"], PANEL if inside else "white")

    # 과정 순서
    cv.rect(tl_x, tl_top, tl_w, tl_h, fill="white", outline=INK, width=2)
    cv.text(tl_x + 16, tl_top + 16 + 10, side["title"], 16, True)
    ly = tl_top + 16 + 22 + 18 + (tl_h - tl_need) / 2
    cv.line([(tl_x + 16 + step / 2, ly), (tl_x + 16 + step * (len(tl_names) - 0.5), ly)], st["spine"], 3)
    for k, (names, info) in enumerate(zip(tl_names, tl_info)):
        mx = tl_x + 16 + step * (k + 0.5)
        cv.circle(mx, ly, 7, fill="white", outline=st["spine"], width=3)
        ty = ly + 14
        for r in names:
            cv.text(mx, ty + r.height / 2, r.text, r.size, r.bold, r.color, "mm")
            ty += r.height
        ty = ly + 14 + name_h + 4
        for r in info:
            cv.text(mx, ty + r.height / 2, r.text, r.size, r.bold, r.color, "mm")
            ty += r.height
    return cv


def main():
    with open(os.path.join(HERE, "roadmap.json"), encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(OUT_DIR, exist_ok=True)
    pages = [("intro", intro_page(data))] + [(p["id"], path_page(data, p)) for p in data["paths"]]
    for name, cv in pages:
        path = os.path.join(OUT_DIR, name + ".png")
        cv.save(path)
        print("%s  %dx%d  %d KB" % (os.path.relpath(path, ROOT), W * OUT, cv.height * OUT, os.path.getsize(path) // 1024))


if __name__ == "__main__":
    main()
