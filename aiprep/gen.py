# -*- coding: utf-8 -*-
"""숫자가 바뀌는 생성기(설계 3.6, 부록 A.3). 차시 문항 폴더의 gens.py 가 이 모듈의 gen·blank·choice·num·fixed·Retry 를 씀.

    from aiprep.gen import gen, blank, num

    @gen("i05-g02", unit="5b", level=2, tags=["Linear 파라미터 수"], ref=["5차시 과제 5번"], facts=["F05-20"],
         basis="lecture-formula", step="5b/3")
    def linear_params(r):
        a, c = r.pick([8, 16, 32]), r.int(1, 10)
        return blank(stem="…", blanks=[{"answer": [str(a * c + c)], "mode": "number"}], explain="…", params={"a": a, "c": c})

공용 계산은 ai/items/common/gens.py 에 @base("batches") 로 한 번 쓰고, 차시마다 register("i10-g03", base="batches",
ranges={…}, unit=…, ref=…, facts=…, family="batches") 로 숫자 범위와 근거만 바꿔 붙임. 생성기 모듈을 읽는 동안 @gen 과
register 가 만든 것을 모아 둠(load_module).

Rng 는 random.Random(seed).random() 의 열만 써서 int·pick·sample·shuffle·chance 를 만듦. 파이썬 문서가 판 사이에 같다고
보장하는 것은 random() 열뿐이라 학생 파이썬 3.10~3.13 과 CI 에서 같은 시드가 같은 문항이 됨. 생성기가 Retry 를 내면
Rng(seed * 1009 + 시도 번호)로 다시 부르고 TRIES 번을 넘기면 GenError 임.
"""
import decimal
import hashlib
import importlib.util
import os
from pathlib import Path
import random
import sys

# 로드한 런타임의 소스를 고정함. 실행 중 디스크 수정은 다음 import부터 반영함.
RUNTIME_SOURCE_HASH = hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode("utf-8")).hexdigest()

TRIES = 50
BASIS = ("lecture-example", "lecture-formula")
_COLLECT = []  # 모듈을 읽는 동안 @gen·register 가 만든 GenSpec
_BASES = {}  # @base 로 등록한 공용 계산


class Retry(Exception):
    """이 시드의 숫자로는 문항을 만들지 않음(정답이 반올림 경계, 보기가 겹침 등). 다음 시드로 다시 부름."""


class GenError(Exception):
    """생성기를 읽거나 돌리지 못함."""


class Rng(object):
    """random() 열만 쓰는 난수. 같은 시드면 파이썬 판과 상관없이 같은 값."""

    def __init__(self, seed):
        self._random = random.Random(seed)

    def random(self):
        return self._random.random()

    def int(self, lo, hi):
        """lo 이상 hi 이하 정수."""
        if hi < lo:
            raise ValueError("int(%r, %r)" % (lo, hi))
        return lo + min(hi - lo, int(self.random() * (hi - lo + 1)))

    def pick(self, seq):
        items = list(seq)
        if not items:
            raise ValueError("빈 목록에서 고를 수 없음")
        return items[min(len(items) - 1, int(self.random() * len(items)))]

    def sample(self, seq, k):
        pool = list(seq)
        if k > len(pool):
            raise ValueError("sample 개수가 목록보다 큼")
        out = []
        for _ in range(k):
            out.append(pool.pop(min(len(pool) - 1, int(self.random() * len(pool)))))
        return out

    def shuffle(self, seq):
        """seq 를 제자리에서 섞고 돌려줌(피셔-예이츠)."""
        for i in range(len(seq) - 1, 0, -1):
            j = min(i, int(self.random() * (i + 1)))
            seq[i], seq[j] = seq[j], seq[i]
        return seq

    def chance(self, p):
        return self.random() < p


class GenSpec(object):
    """생성기 하나. id, fn(Rng 를 받아 문항 dict 를 돌려줌), meta(unit, level, tags, ref, facts, basis, step, core, prio,
    family, confuse, deep, errata), doc(독스트링), path(선언한 파일)."""

    def __init__(self, gid, fn, meta, doc="", path=""):
        self.id, self.fn, self.meta, self.doc, self.path = gid, fn, meta, doc or "", path

    def __repr__(self):
        return "GenSpec(%r)" % self.id


def _meta(unit, level, tags, ref, facts, basis, step, core, prio, family, confuse, deep, errata, base_name=None):
    return {"unit": unit, "level": int(level), "tags": list(tags or []), "ref": list(ref or []), "facts": list(facts or []),
            "basis": basis, "step": step, "core": bool(core), "prio": int(prio), "family": family, "confuse": list(confuse or []),
            "deep": bool(deep), "errata": list(errata or []), "base": base_name}


def gen(gid, unit, level=2, tags=(), ref=(), facts=(), basis=None, step=None, core=False, prio=2, family=None, confuse=(),
        deep=False, errata=()):
    """생성기 선언. 꾸민 함수는 Rng 하나를 받아 blank(...) 나 choice(...) 를 돌려줌."""
    def wrap(fn):
        spec = GenSpec(gid, fn, _meta(unit, level, tags, ref, facts, basis, step, core, prio, family, confuse, deep, errata),
                       fn.__doc__, getattr(sys.modules.get(fn.__module__), "__file__", ""))
        fn.gen_spec = spec
        _COLLECT.append(spec)
        return fn
    return wrap


def base(name):
    """공용 계산 선언(ai/items/common/gens.py). 꾸민 함수는 (Rng, ranges) 를 받음."""
    def wrap(fn):
        _BASES[name] = fn
        return fn
    return wrap


def register(gid, base, unit, ranges=None, level=2, tags=(), ref=(), facts=(), basis=None, step=None, core=False, prio=2,
             family=None, confuse=(), deep=False, errata=()):
    """공용 계산 base 에 숫자 범위 ranges 와 근거만 바꿔 붙인 생성기. family 를 주지 않으면 base 이름을 씀."""
    ranges = dict(ranges or {})

    def run(r):
        fn = _BASES.get(base)
        if fn is None:
            raise GenError("공용 생성기 %s 가 없습니다(ai/items/common/gens.py)." % base)
        return fn(r, ranges)

    meta = _meta(unit, level, tags, ref, facts, basis, step, core, prio, family or base, confuse, deep, errata, base)
    meta["ranges"] = ranges
    frame = sys._getframe(1)
    spec = GenSpec(gid, run, meta, "공용 생성기 %s 의 차시 판. 범위 %s" % (base, ranges), frame.f_globals.get("__file__", ""))
    _COLLECT.append(spec)
    return spec


def bases():
    return dict(_BASES)


# 생성기가 돌려주는 문항

def blank(stem, blanks, explain, params=None, **extra):
    out = {"kind": "blank", "stem": stem, "blanks": [dict(b) for b in blanks], "explain": explain, "params": dict(params or {})}
    out.update(extra)
    return out


def choice(stem, options, pick="right", multi=False, explain="", params=None, **extra):
    """options 는 [(글, 참인지, 까닭)] 이나 [{"text", "ok", "why"}]."""
    rows = []
    for option in options:
        if isinstance(option, dict):
            rows.append({"text": option["text"], "ok": bool(option.get("ok")), "why": option.get("why", "")})
        else:
            text, ok, why = (list(option) + [""])[:3]
            rows.append({"text": text, "ok": bool(ok), "why": why})
    out = {"kind": "choice", "stem": stem, "options": rows, "pick": pick, "multi": bool(multi), "explain": explain,
           "params": dict(params or {})}
    out.update(extra)
    return out


def num(x):
    """천 단위 쉼표를 붙인 숫자 글. 정수가 아닌 값은 뒤의 0 을 뗌."""
    if isinstance(x, int) or (isinstance(x, float) and x.is_integer()):
        return "{:,}".format(int(x))
    text = format(decimal.Decimal(str(x)).normalize(), "f")
    head, _, tail = text.partition(".")
    return "{:,}".format(int(head)) + ("." + tail if tail else "") if head.lstrip("-").isdigit() else text


def fixed(x, k):
    """x 를 소수 k 자리 글로(반올림). 버리는 첫 자리가 4·5·6 이면 손계산과 반올림이 갈릴 수 있어 Retry."""
    value = decimal.Decimal(str(x))
    digits = value.quantize(decimal.Decimal(1).scaleb(-(k + 1)), rounding=decimal.ROUND_DOWN)
    last = abs(int(digits.scaleb(k + 1))) % 10
    if last in (4, 5, 6):
        raise Retry("반올림 경계")
    return str(value.quantize(decimal.Decimal(1).scaleb(-k), rounding=decimal.ROUND_HALF_UP))


# 읽기와 돌리기

def _exec(path, name):
    """파일 하나를 모듈로 돌림. 은행 폴더에 __pycache__ 가 생기지 않게 바이트코드를 쓰지 않음(서명 해시에 섞이지 않게)."""
    keep = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = keep


def load_module(path, name=None):
    """생성기 파일 하나를 읽어 그 안에서 선언한 GenSpec 목록을 돌려줌. 파일이 없으면 빈 목록."""
    if not os.path.isfile(path):
        return []
    name = name or "ai_gens_%d" % abs(hash(os.path.abspath(path)))
    start = len(_COLLECT)
    try:
        _exec(path, name)
    except Exception as error:  # noqa: BLE001 - 출제 파일의 어떤 오류든 이유만 보여 줌
        del _COLLECT[start:]
        raise GenError("%s 을 읽을 수 없습니다: %s: %s" % (os.path.basename(path), type(error).__name__, error))
    found = _COLLECT[start:]
    del _COLLECT[start:]
    for item in found:
        item.path = os.path.abspath(path)
    return found


def load_oracle(path):
    """oracle.py 를 읽어 {함수 이름: 함수}. 함수 이름은 생성기 id 의 붙임표를 밑줄로 바꾼 것(i05_g02)."""
    if not os.path.isfile(path):
        return {}
    try:
        module = _exec(path, "ai_oracle_%d" % abs(hash(os.path.abspath(path))))
    except Exception as error:  # noqa: BLE001
        raise GenError("%s 을 읽을 수 없습니다: %s: %s" % (os.path.basename(path), type(error).__name__, error))
    return {name: fn for name, fn in vars(module).items() if callable(fn) and not name.startswith("_")}


def oracle_name(gid):
    return gid.replace("-", "_")


def run(spec, seed, tries=TRIES):
    """seed 로 생성기를 돌린 문항 dict. 꼴은 정적 문항과 같고 id, seed, params 가 붙음."""
    for attempt in range(tries):
        rng = Rng(seed if attempt == 0 else seed * 1009 + attempt)
        try:
            out = spec.fn(rng)
        except Retry:
            continue
        if not isinstance(out, dict) or out.get("kind") not in ("blank", "choice"):
            raise GenError("%s 가 blank(...) 나 choice(...) 를 돌려주지 않았습니다." % spec.id)
        out = dict(out, id=spec.id, seed=seed)
        return out
    raise GenError("%s 가 %d번 다시 해도 문항을 만들지 못했습니다(시드 %s)." % (spec.id, tries, seed))
