# -*- coding: utf-8 -*-
"""알고리즘 여행 서비스. 화면은 JourneySession 만 부름. 반환은 dict·list, 오류는 사용자에게 그대로 보여 줄 JourneyError.

진행 기록은 submissions/<ID>/journey/progress.json 에 덧붙기만 하고, 통과·잠금·추천 같은 상태는 기록에서 그때그때
계산함. 잠금(RLock)은 progress.json 쓰기와 봉인 캐시에만 걸고, 오래 걸리는 실행·채점은 잠금 밖에서 함.
만들 때는 Node 를 찾지 않음. JavaScript 를 처음 물을 때 찾고 결과는 journey.node 가 프로세스 안에서 기억함.
"""
import datetime
import json
import os
import platform
import threading

import adaptive
import session
import study
from journey import bank, grading, runner, values
from journey import node as node_finder

ROLE_LABEL = {"basic": "기초", "mid": "중급", "side": "선택", "boss": "보스"}
FILE_NAME = {"python": "solution.py", "javascript": "solution.js"}
MAX_CASES = 20
RECENT = 5
ACTIVITY_DAYS = 14
NO_NODE = ("Node.js 를 찾지 못했습니다. Node.js %d 이상을 설치한 뒤 [다시 찾기]를 누르거나 [Node 위치 지정…]으로 "
           "node 실행 파일을 골라 주세요." % node_finder.MIN_MAJOR)


class JourneyError(session.SessionError):
    """사용자에게 그대로 보여 줄 수 있는 여정 오류."""


def today():
    return datetime.date.today()


def _blank_state():
    return {"attempts": 0, "best": {}, "passed_langs": [], "passed": False, "first_pass_at": None, "hints": 0,
            "explained": False, "explained_first": False, "tried": False}


def states(log):
    """기록에서 문제별 상태를 계산함. {"d01/p1": {attempts, best, passed_langs, passed, first_pass_at, hints,
    explained, explained_first, tried}}. explained_first 는 해설 기록이 첫 통과보다 앞선 것임(해설 보고 통과)."""
    found, first_pass, first_explain = {}, {}, {}
    for index, entry in enumerate(log):
        item, kind = entry.get("item"), entry.get("kind")
        state = found.setdefault(item, _blank_state())
        if kind == "grade":
            state["attempts"] += 1
            state["tried"] = True
            lang, score = entry.get("lang"), entry.get("score") or 0.0
            if lang in values.LANGS:
                state["best"][lang] = max(state["best"].get(lang, 0.0), score)
            if entry.get("passed"):
                if lang in values.LANGS and lang not in state["passed_langs"]:
                    state["passed_langs"].append(lang)
                if item not in first_pass:
                    first_pass[item] = index
                    state["first_pass_at"] = entry.get("at")
        elif kind == "hint":
            state["hints"] = max(state["hints"], int(entry.get("level") or 0))
        elif kind == "explain":
            state["explained"] = True
            first_explain.setdefault(item, index)
    for item, state in found.items():
        state["passed"] = item in first_pass
        state["passed_langs"] = [lang for lang in values.LANGS if lang in state["passed_langs"]]
        state["explained_first"] = item in first_pass and first_explain.get(item, len(log)) < first_pass[item]
    return found


class JourneySession:
    def __init__(self, user, node_path=None):
        """은행과 progress.json 을 읽음. progress.json 이 깨졌거나 index.json 을 읽지 못하면 JourneyError."""
        if not session.valid_user(user):
            raise JourneyError("ID 가 올바르지 않습니다: %r" % (user,))
        self.user = user
        self.node_path = node_path or None
        self._lock = threading.RLock()
        self._secrets = {}
        self.folder = os.path.join(study.SUBMISSIONS_DIR, user, "journey")
        self.progress_path = os.path.join(self.folder, "progress.json")
        self.root = bank.BANK_DIR
        try:
            self.index = bank.read_index(self.root)
        except bank.BankError as error:
            raise JourneyError("알고리즘 여행 목록을 읽을 수 없습니다. %s" % error)
        self.dungeons, self.errors, self.bank_errors = {}, {}, []
        for entry in self.index:
            if not bank.is_ready(entry["id"], self.root):
                continue
            try:
                self.dungeons[entry["id"]] = bank.load_dungeon(entry, self.root)
            except bank.BankError as error:
                self.errors[entry["id"]] = str(error)
                self.bank_errors.append("%s: %s" % (entry["id"], error))
        self._reload()

    # 진행 기록

    def _load(self):
        """progress.json 전체. 없으면 None, 깨졌으면 JourneyError."""
        if not os.path.isfile(self.progress_path):
            return None
        try:
            data = study.read_json(self.progress_path)
            log = data["log"]
            if not isinstance(log, list) or not all(isinstance(e, dict) and "kind" in e and "item" in e for e in log):
                raise ValueError("log 항목의 형식이 맞지 않습니다")
        except json.JSONDecodeError as error:
            raise JourneyError("알고리즘 여행 기록(journey/progress.json)을 읽을 수 없습니다: %d번째 줄 %d번째 글자 근처의 JSON 형식이 "
                               "맞지 않습니다." % (error.lineno, error.colno))
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise JourneyError("알고리즘 여행 기록(journey/progress.json)을 읽을 수 없습니다: %s" % error)
        return data

    def _append(self, entry):
        """잠금 안에서 progress.json 을 다시 읽고 한 줄 덧붙여 씀. 처음이면 파일을 만듦."""
        with self._lock:
            data = self._load() or {"format": 1, "user": self.user, "created": adaptive.now(), "log": []}
            record = dict({"at": adaptive.now()}, **entry)
            data["log"].append(record)
            try:
                study.write_text(self.progress_path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")
            except OSError as error:
                raise JourneyError("알고리즘 여행 기록을 저장하지 못했습니다. 기록은 바뀌지 않았으니 잠시 뒤 다시 해 주세요.\n%s" % error)
            self.log = data["log"]
            return record

    def _reload(self):
        with self._lock:
            self.log = (self._load() or {"log": []})["log"]

    def _states(self):
        return states(self.log)

    # 은행

    def _entry(self, did):
        entry = next((e for e in self.index if e["id"] == did), None)
        if entry is None:
            raise JourneyError("던전 %s 를 찾을 수 없습니다." % did)
        return entry

    def _dungeon(self, did):
        self._entry(did)
        if did in self.errors:
            raise JourneyError("던전 %s 를 읽을 수 없습니다. %s" % (did, self.errors[did]))
        if did not in self.dungeons:
            raise JourneyError("아직 출제되지 않은 던전입니다.")
        return self.dungeons[did]

    def _problem(self, did, pid):
        dungeon = self._dungeon(did)
        problem = next((p for p in dungeon["problems"] if p["id"] == pid), None)
        if problem is None:
            raise JourneyError("문제 %s/%s 를 찾을 수 없습니다." % (did, pid))
        return dungeon, problem

    def _open_problem(self, did, pid, found=None):
        """잠긴 보스면 JourneyError."""
        dungeon, problem = self._problem(did, pid)
        if problem["role"] == "boss":
            found = self._states() if found is None else found
            if not self.boss_open(dungeon, found):
                done, total = self._mid_count(dungeon, found)
                raise JourneyError("보스 문제는 중급 문제를 모두 통과하면 열립니다(%d개 중 %d개 통과)." % (total, done))
        return dungeon, problem

    def _secret_files(self, did):
        with self._lock:
            if did not in self._secrets:
                try:
                    self._secrets[did] = bank.load_secrets(self._dungeon(did)["dir"])
                except bank.BankError as error:
                    raise JourneyError("던전 %s 의 봉인 파일을 풀 수 없습니다. %s" % (did, error))
            return self._secrets[did]

    def _secret_json(self, did, rel):
        try:
            return bank.secret_json(self._secret_files(did), rel)
        except bank.BankError as error:
            raise JourneyError(str(error))

    def _hints(self, did, pid):
        return bank.parse_hints(self._secret_files(did).get(pid + "/hints.md"))

    # 잠금 규칙

    @staticmethod
    def _item(did, pid):
        return "%s/%s" % (did, pid)

    def _state(self, found, did, pid):
        return found.get(self._item(did, pid)) or _blank_state()

    def _mid_count(self, dungeon, found):
        mids = [p for p in dungeon["problems"] if p["role"] == "mid"]
        done = sum(1 for p in mids if self._state(found, dungeon["id"], p["id"])["passed"])
        return done, len(mids)

    def boss_open(self, dungeon, found=None):
        """보스는 그 던전의 중급(mid) 문제를 모두 통과하면 열림(중급이 없으면 열림). 기초와 선택은 세지 않음."""
        found = self._states() if found is None else found
        done, total = self._mid_count(dungeon, found)
        return done == total

    def _boss(self, dungeon):
        return dungeon["problems"][-1]

    def _cleared(self, dungeon, found):
        return self._state(found, dungeon["id"], self._boss(dungeon)["id"])["passed"]

    def _next(self, found):
        """index 순서로 클리어하지 않은 첫 던전에서 통과하지 않은 첫 문제. 선택 문제와 잠긴 보스는 건너뜀."""
        for entry in self.index:
            dungeon = self.dungeons.get(entry["id"])
            if not dungeon or self._cleared(dungeon, found):
                continue
            opened = self.boss_open(dungeon, found)
            for problem in dungeon["problems"]:
                if problem["role"] == "side" or (problem["role"] == "boss" and not opened):
                    continue
                if not self._state(found, dungeon["id"], problem["id"])["passed"]:
                    return {"did": dungeon["id"], "pid": problem["id"], "no": problem["no"], "title": problem["title"],
                            "role": problem["role"]}
        return None

    # 읽기

    def overview(self):
        found = self._states()
        rows, ready, cleared, passed, total = [], 0, 0, 0, 0
        by_lang = {lang: 0 for lang in values.LANGS}
        for entry in self.index:
            dungeon = self.dungeons.get(entry["id"])
            row = dict(entry, ready=bool(dungeon), error=self.errors.get(entry["id"], ""), cleared=False, passed=0,
                       total=0, boss_open=False, progress=0.0)
            if dungeon:
                ready += 1
                states_here = [self._state(found, entry["id"], p["id"]) for p in dungeon["problems"]]
                row["passed"] = sum(1 for s in states_here if s["passed"])
                row["total"] = len(states_here)
                row["cleared"] = self._cleared(dungeon, found)
                row["boss_open"] = self.boss_open(dungeon, found)
                row["progress"] = row["passed"] / float(row["total"]) if row["total"] else 0.0
                cleared += row["cleared"]
                passed += row["passed"]
                total += row["total"]
                for s in states_here:
                    for lang in s["passed_langs"]:
                        by_lang[lang] += 1
            rows.append(row)
        return {"dungeons": rows, "ready": ready, "cleared": cleared, "passed": passed, "total": total,
                "by_lang": by_lang, "explained_first": sum(1 for s in found.values() if s["explained_first"]),
                "hints": sum(s["hints"] for s in found.values()),
                "attempts": sum(1 for e in self.log if e.get("kind") == "grade"),
                "recent": self._recent(), "next": self._next(found), "activity": self._activity(),
                "bank_errors": list(self.bank_errors)}

    def _recent(self):
        grades = [e for e in self.log if e.get("kind") == "grade"][-RECENT:]
        rows = []
        for entry in reversed(grades):
            did, _, pid = str(entry.get("item")).partition("/")
            problem = None
            if did in self.dungeons:
                problem = next((p for p in self.dungeons[did]["problems"] if p["id"] == pid), None)
            rows.append({"item": entry.get("item"), "did": did, "pid": pid, "no": problem["no"] if problem else entry.get("item"),
                         "title": problem["title"] if problem else "", "lang": entry.get("lang"),
                         "score": entry.get("score"), "passed": bool(entry.get("passed")), "at": entry.get("at")})
        return rows

    def _activity(self):
        """최근 14일(오늘 포함)의 날짜별 채점 수. 채점이 없는 날도 0 으로 들어감."""
        end = today()
        days = [(end - datetime.timedelta(days=back)).isoformat() for back in range(ACTIVITY_DAYS - 1, -1, -1)]
        counts = dict.fromkeys(days, 0)
        for entry in self.log:
            day = str(entry.get("at") or "")[:10]
            if entry.get("kind") == "grade" and day in counts:
                counts[day] += 1
        return counts

    def _row(self, dungeon, problem, found, opened):
        state = self._state(found, dungeon["id"], problem["id"])
        return {"id": problem["id"], "no": problem["no"], "role": problem["role"], "role_label": ROLE_LABEL[problem["role"]],
                "title": problem["title"], "tier": problem["tier"], "passed": state["passed"],
                "passed_langs": list(state["passed_langs"]), "best": dict(state["best"]), "tried": state["tried"],
                "attempts": state["attempts"], "hints": state["hints"], "explained": state["explained"],
                "explained_first": state["explained_first"], "locked": problem["role"] == "boss" and not opened,
                "prep": self._refs(dungeon, problem["prep"], found)}

    def _refs(self, dungeon, pids, found):
        """준비 문제·보스에 쓰는 문제 목록. 없는 id 는 건너뜀."""
        rows = []
        for pid in pids:
            problem = next((p for p in dungeon["problems"] if p["id"] == pid), None)
            if problem:
                rows.append({"pid": pid, "no": problem["no"], "title": problem["title"],
                             "passed": self._state(found, dungeon["id"], pid)["passed"]})
        return rows

    def dungeon(self, did):
        """지도 오른쪽 상세(6.4). 출제되지 않은 던전은 ready False 와 빈 problems. boss_new 는 보스를 통과했거나
        보스 해설이 열렸을 때만 보스의 extra.json 에서 읽어 넣고, 그 밖에는 None."""
        entry = self._entry(did)
        dungeon = self.dungeons.get(did)
        result = dict(entry, ready=bool(dungeon), error=self.errors.get(did, ""), intro="", base_dir=None, skills=[],
                      boss_new=None, cleared=False, boss_open=False, passed=0, total=0, mid_passed=0, mid_total=0,
                      problems=[])
        if not dungeon:
            return result
        found = self._states()
        opened = self.boss_open(dungeon, found)
        rows = [self._row(dungeon, problem, found, opened) for problem in dungeon["problems"]]
        done, mids = self._mid_count(dungeon, found)
        boss = self._state(found, did, self._boss(dungeon)["id"])
        result.update(intro=dungeon["intro"], base_dir=dungeon["dir"], skills=list(dungeon["skills"]),
                      cleared=boss["passed"], boss_open=opened, passed=sum(1 for row in rows if row["passed"]),
                      total=len(rows), mid_passed=done, mid_total=mids, problems=rows)
        if boss["passed"] or boss["explained"]:
            try:
                extra = self._secret_json(did, self._boss(dungeon)["id"] + "/extra.json") or {}
                result["boss_new"] = extra.get("boss_new") or None
            except JourneyError:
                result["boss_new"] = None
        return result

    def _code_path(self, did, pid, lang):
        return os.path.join(self.folder, did, pid + runner.EXT[lang])

    def _cases_path(self, did, pid):
        return os.path.join(self.folder, did, pid + ".cases.json")

    def _read_cases(self, problem, did, pid):
        """내가 추가한 테스트 케이스. 파일이 없거나 깨졌으면 빈 목록, 타입이 맞지 않는 줄은 뺌."""
        path = self._cases_path(did, pid)
        try:
            raw = study.read_json(path)["cases"]
        except (OSError, ValueError, KeyError, TypeError):
            return []
        cases = []
        for case in raw if isinstance(raw, list) else []:
            try:
                cases.append(clean_case(problem, case))
            except ValueError:
                continue
        return cases[:MAX_CASES]

    def problem(self, did, pid, lang):
        """문제 화면(6.5)이 쓰는 모든 것. 잠긴 보스면 JourneyError."""
        check_lang(lang)
        found = self._states()
        dungeon, problem = self._open_problem(did, pid, found)
        state = self._state(found, did, pid)
        hints = self._hints(did, pid)
        starter = values.starter(problem["signature"], lang)
        path = self._code_path(did, pid, lang)
        code = starter
        if os.path.isfile(path):
            try:
                code = study.read_text(path)
            except (OSError, ValueError) as error:
                raise JourneyError("코드 파일을 읽을 수 없습니다: %s" % error)
        return {"did": did, "pid": pid, "no": problem["no"], "role": problem["role"], "role_label": ROLE_LABEL[problem["role"]],
                "title": problem["title"], "tier": problem["tier"], "markdown": problem["markdown"], "base_dir": dungeon["dir"],
                "dungeon_no": dungeon["no"], "dungeon_title": dungeon["title"], "signature": problem["signature"],
                "examples": problem["examples"], "time_limit_ms": dict(problem["time_limit_ms"]),
                "limit_note": grading.limit_note(problem), "lang": lang, "file_name": FILE_NAME[lang], "code": code,
                "starter": starter, "prep": self._refs(dungeon, problem["prep"], found),
                "uses": self._refs(dungeon, problem["uses"], found), "cases": self._read_cases(problem, did, pid),
                "hints": hints[:state["hints"]], "hint_total": len(hints), "explain_open": state["passed"] or state["explained"],
                "passed": state["passed"], "passed_langs": list(state["passed_langs"]), "best": dict(state["best"]),
                "attempts": state["attempts"], "explained": state["explained"], "explained_first": state["explained_first"]}

    def runtime(self, lang):
        """{"ok", "label", "problem"}. javascript 를 처음 물을 때 node 를 찾음(만들 때는 찾지 않음)."""
        check_lang(lang)
        if lang == "python":
            return {"ok": True, "label": "Python %s" % platform.python_version(), "problem": ""}
        found = node_finder.find(saved=self.node_path)
        if not found:
            return {"ok": False, "label": "", "problem": NO_NODE}
        return {"ok": True, "label": "Node.js %s" % found["version"], "problem": "", "path": found["path"]}

    def node_checked(self):
        """node 를 이미 찾아 봤는지. True 면 runtime("javascript") 가 node 를 띄우지 않고 기억한 결과를 바로 돌려줌."""
        return node_finder.searched()

    def cache_info(self):
        return runner.cache_info()

    # 쓰기

    def save_code(self, did, pid, lang, text):
        """코드를 저장함. 파일이 아직 없고 시작 코드와 같으면 만들지 않음(보기만 한 문제는 파일이 생기지 않음)."""
        check_lang(lang)
        _, problem = self._problem(did, pid)
        text = session.clean_text(text)
        path = self._code_path(did, pid, lang)
        if not os.path.isfile(path) and text == values.starter(problem["signature"], lang):
            return
        self._write(path, text, "코드를")

    def reset_code(self, did, pid, lang):
        """시작 코드로 되돌림. 코드 파일이 있으면 시작 코드로 덮어씀."""
        check_lang(lang)
        _, problem = self._problem(did, pid)
        starter = values.starter(problem["signature"], lang)
        path = self._code_path(did, pid, lang)
        if os.path.isfile(path):
            self._write(path, starter, "코드를")
        return starter

    def save_cases(self, did, pid, cases):
        """테스트 케이스를 검사해 저장하고 정리된 목록을 돌려줌. 틀리면 JourneyError(몇 번째 케이스가 왜)."""
        _, problem = self._problem(did, pid)
        if len(cases) > MAX_CASES:
            raise JourneyError("테스트 케이스는 %d개까지 추가할 수 있습니다." % MAX_CASES)
        cleaned = []
        for number, case in enumerate(cases, 1):
            try:
                cleaned.append(clean_case(problem, case))
            except ValueError as error:
                raise JourneyError("%d번 케이스의 %s" % (number, error))
        path = self._cases_path(did, pid)
        if cleaned or os.path.isfile(path):
            self._write(path, json.dumps({"cases": cleaned}, ensure_ascii=False, indent=1) + "\n", "테스트 케이스를")
        return cleaned

    def _write(self, path, text, what):
        try:
            study.write_text(path, text)
        except OSError as error:
            raise JourneyError("%s 저장하지 못했습니다: %s" % (what, error))

    def reveal_hint(self, did, pid):
        """다음 힌트를 열고 기록함. {"level", "text", "left"}. 다 열었으면 JourneyError."""
        with self._lock:
            self._reload()
            self._open_problem(did, pid)
            hints = self._hints(did, pid)
            level = self._state(self._states(), did, pid)["hints"]
            if not hints:
                raise JourneyError("이 문제에는 힌트가 없습니다.")
            if level >= len(hints):
                raise JourneyError("힌트를 모두 열었습니다.")
            self._append({"kind": "hint", "item": self._item(did, pid), "level": level + 1})
        return {"level": level + 1, "text": hints[level], "left": len(hints) - level - 1}

    def open_explain(self, did, pid, lang, give_up=False):
        """해설을 엶. 통과했거나 이미 연 문제는 그대로 열고, 아니면 give_up=True 일 때만 열며 explain 기록을 남김.
        {"markdown", "solution": {"python", "javascript"}, "parts", "similar", "base_dir"}. parts·similar 는 extra.json 에서 옴."""
        check_lang(lang)
        with self._lock:
            self._reload()
            dungeon, problem = self._open_problem(did, pid)
            state = self._state(self._states(), did, pid)
            if not (state["passed"] or state["explained"]):
                if not give_up:
                    raise JourneyError("이 문제를 통과하거나 [포기하고 해설 보기]를 눌러야 해설이 열립니다.")
            secrets = self._secret_files(did)
            markdown = secrets.get(pid + "/explain.md")
            if markdown is None:
                raise JourneyError("이 문제의 해설 파일을 찾을 수 없습니다.")
            extra = self._secret_json(did, pid + "/extra.json") or {}
            if not (state["passed"] or state["explained"]):
                self._append({"kind": "explain", "item": self._item(did, pid)})
        parts = []
        for part in extra.get("parts") or []:
            sources = list(part.get("from") or [])
            parts.append({"text": part.get("text", ""), "from": sources,
                          "nos": [ref["no"] for ref in self._refs(dungeon, sources, {})]})
        similar = []
        for item in extra.get("similar") or []:
            row = dict(item)
            if row.get("site") == "boj" and row.get("id") and not row.get("url"):
                row["url"] = "https://www.acmicpc.net/problem/%s" % row["id"]
            row.setdefault("url", None)
            similar.append(row)
        return {"markdown": markdown,
                "solution": {lang_: secrets.get(pid + "/" + FILE_NAME[lang_]) or "" for lang_ in values.LANGS},
                "parts": parts, "similar": similar, "base_dir": dungeon["dir"]}

    def set_node(self, path):
        """사용자가 고른 node 를 확인해 기억함. runtime("javascript") 모양을 돌려주고, 쓸 수 없으면 JourneyError."""
        try:
            info = node_finder.check(path)
        except ValueError as error:
            raise JourneyError(str(error))
        node_finder.remember(info)
        self.node_path = path
        return self.runtime("javascript")

    def find_node(self, probe=True):
        """[다시 찾기]. 기억한 결과를 버리고 다시 찾음. probe 면 마지막에 로그인 셸에도 물음."""
        node_finder.forget()
        node_finder.find(probe=probe, saved=self.node_path)
        return self.runtime("javascript")

    def clear_cache(self):
        return runner.clear_cache()

    # 실행

    def _node_for(self, lang):
        if lang != "javascript":
            return None
        found = node_finder.find(saved=self.node_path)
        if not found:
            raise JourneyError(NO_NODE)
        return found

    def _source(self, did, pid, lang, problem, tmp):
        """실행할 코드 파일. 아직 없으면 시작 코드를 tmp 에 써서 그 경로를 돌려줌."""
        path = self._code_path(did, pid, lang)
        if os.path.isfile(path):
            return path
        path = os.path.join(tmp, "starter" + runner.EXT[lang])
        study.write_text(path, values.starter(problem["signature"], lang))
        return path

    def run(self, did, pid, lang, report=None, cancel=None):
        """[코드 실행]: examples 와 내가 추가한 케이스. 기록하지 않음. 결과 모양은 명세 4.1."""
        check_lang(lang)
        _, problem = self._open_problem(did, pid)
        node = self._node_for(lang)
        mine = self._read_cases(problem, did, pid)
        try:
            with runner.workspace() as tmp:
                result = grading.run(problem, lang, self._source(did, pid, lang, problem, tmp), mine, report, cancel, node)
        except (OSError, RuntimeError) as error:
            raise JourneyError("코드를 실행하지 못했습니다. %s" % error)
        result["runtime"] = self.runtime(lang)["label"]
        return result

    def grade(self, did, pid, lang, report=None, cancel=None):
        """[제출 후 채점하기]. 끝까지 돌면 grade 기록 한 줄을 남기고, 취소되면 기록하지 않음. 결과 모양은 명세 4.2."""
        check_lang(lang)
        self._reload()
        before = self._states()
        dungeon, problem = self._open_problem(did, pid, before)
        node = self._node_for(lang)
        tests = self._secret_json(did, pid + "/tests.json")
        if tests is None:
            raise JourneyError("이 문제의 채점 파일(tests.json)을 찾을 수 없습니다.")
        gen_source = self._secret_files(did).get(pid + "/gen.py")
        state = self._state(before, did, pid)
        reveal = state["passed"] or state["explained"]
        try:
            with runner.workspace() as tmp:
                result = grading.grade(problem, problem["role"], tests, gen_source, lang,
                                       self._source(did, pid, lang, problem, tmp), report, cancel, node, reveal)
        except runner.GenError as error:
            raise JourneyError("테스트 입력을 만들지 못했습니다. %s" % error)
        except bank.BankError as error:
            raise JourneyError("이 문제의 채점 파일이 올바르지 않습니다. %s" % error)
        except (OSError, RuntimeError) as error:
            raise JourneyError("채점하지 못했습니다. %s" % error)
        result.update(runtime=self.runtime(lang)["label"], first_pass=False, boss_opened=False, cleared=False)
        if result["cancelled"]:
            return result
        entry = {"kind": "grade", "item": self._item(did, pid), "lang": lang, "score": result["score"], "acc": result["acc"],
                 "eff": result["eff"], "passed": result["passed"], "tests": result["tests"]}
        if result["fatal"]:
            entry["fatal"] = result["fatal"].get("kind")
        self._append(entry)
        after = self._states()
        if result["passed"] and not state["passed"]:
            result["first_pass"] = True
            result["cleared"] = problem["role"] == "boss"
            result["boss_opened"] = (problem["role"] == "mid" and not self.boss_open(dungeon, before)
                                     and self.boss_open(dungeon, after))
        return result


def check_lang(lang):
    if lang not in values.LANGS:
        raise JourneyError("언어는 python 이나 javascript 여야 합니다: %r" % (lang,))


def clean_case(problem, case):
    """테스트 케이스 하나를 검사해 {"args", "expected"} 로. 틀리면 ValueError(어느 칸이 왜)."""
    params, returns = problem["signature"]["params"], problem["signature"]["returns"]
    if not isinstance(case, dict):
        raise ValueError("형식이 맞지 않습니다.")
    args = case.get("args")
    if not isinstance(args, list) or len(args) != len(params):
        raise ValueError("인자가 %d개여야 합니다." % len(params))
    for param, value in zip(params, args):
        problem_text = values.check(value, param["type"])
        if problem_text:
            raise ValueError("%s 칸: %s" % (param["name"], problem_text))
    if "expected" not in case:
        raise ValueError("기댓값 칸이 비어 있습니다.")
    problem_text = values.check(case["expected"], returns)
    if problem_text:
        raise ValueError("기댓값 칸: %s" % problem_text)
    return {"args": list(args), "expected": case["expected"]}
