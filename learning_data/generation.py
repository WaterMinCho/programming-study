# -*- coding: utf-8 -*-
"""생성 문항의 관찰 조건만 수집·서버·공통 입력에서 같은 형식으로 다룸."""
import copy
import json
import math
import re


VERSION = 1
FIELDS = {"version", "generator_id", "template_id", "template_revision", "source_hashes",
          "version_hash", "seed", "params", "params_status", "instance_id"}
DISPLAY_FIELDS = ("stem", "kind", "pick", "multi", "blanks", "options")
RESERVED_PARAMS = {"answer", "answers", "explain", "explanation", "solution", "solutions",
                   "response", "responses", "target", "result", "ok", "why", "right"}
IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
HASH = re.compile(r"[a-f0-9]{64}\Z")


def valid_param_name(key):
    return (isinstance(key, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,47}", key) is not None
            and key.lower() not in RESERVED_PARAMS)


def validate_declaration(meta):
    """버전은 문자열로 선언함. 키 오타·예약어·잘못된 목록은 문항을 내기 전에 확인함."""
    for key in ("template_id", "template_revision"):
        value = meta.get(key)
        if value is not None and (not isinstance(value, str) or not IDENTIFIER.fullmatch(value)):
            raise ValueError("%s에는 영문·숫자·._:-로 된 1~128자 문자열을 적어 주세요." % key)
    names = meta.get("display_params")
    if names is not None and (not isinstance(names, (list, tuple)) or len(names) > 32
                              or any(not valid_param_name(name) for name in names) or len(set(names)) != len(names)):
        raise ValueError("display_params에는 예약어를 제외한 서로 다른 표시 조건 키를 32개까지 적어 주세요.")


def safe_value(value, depth=0):
    """숫자·짧은 문자열·불리언·배열만 허용함. 값의 의미는 출제자가 표시 조건으로 선언함."""
    if value is None or type(value) is bool:
        return True
    if type(value) is int:
        return abs(value) <= 2 ** 53 - 1
    if type(value) is float:
        return math.isfinite(value) and abs(value) <= 2 ** 53 - 1
    if isinstance(value, str):
        return len(value) <= 128 and not any(ord(char) < 32 for char in value)
    return (isinstance(value, list) and depth < 3 and len(value) <= 64
            and all(safe_value(part, depth + 1) for part in value))


def validate(value):
    """새 필드는 엄격히 확인함. 예전 기록에 없는 provenance는 호출자가 None으로 유지함."""
    if not isinstance(value, dict) or set(value) != FIELDS or type(value["version"]) is not int or value["version"] != VERSION:
        raise ValueError("생성 문항의 출처 형식을 확인해 주세요.")
    for key in ("generator_id", "template_id"):
        if not isinstance(value[key], str) or not IDENTIFIER.fullmatch(value[key]):
            raise ValueError("생성기와 템플릿 ID를 확인해 주세요.")
    revision = value["template_revision"]
    if revision is not None and (not isinstance(revision, str) or not IDENTIFIER.fullmatch(revision)):
        raise ValueError("템플릿 버전을 확인해 주세요.")
    hashes = value["source_hashes"]
    if not isinstance(hashes, dict) or set(hashes) != {"generator", "common", "runtime"}:
        raise ValueError("생성 소스 해시의 목록을 확인해 주세요.")
    for key, checksum in {**hashes, "version_hash": value["version_hash"], "instance_id": value["instance_id"]}.items():
        if key == "common" and checksum is None:
            continue
        if not isinstance(checksum, str) or not HASH.fullmatch(checksum):
            raise ValueError("생성 소스와 문항 해시를 확인해 주세요.")
    if type(value["seed"]) is not int or not 0 <= value["seed"] < 2 ** 31:
        raise ValueError("생성 문항의 시드를 확인해 주세요.")
    params = value["params"]
    if not isinstance(params, dict) or len(params) > 32 or any(
            not valid_param_name(key) or not safe_value(part) for key, part in params.items()):
        raise ValueError("표시 조건에는 선언한 이름과 안전한 값만 넣어 주세요.")
    if value["params_status"] not in ("declared", "undeclared") or (value["params_status"] == "undeclared" and params):
        raise ValueError("표시 조건의 선언 상태를 확인해 주세요.")
    if len(json.dumps(params, ensure_ascii=False).encode("utf-8")) > 8192:
        raise ValueError("표시 조건의 크기를 확인해 주세요.")
    return copy.deepcopy(value)


def instance_id(value, display):
    """답·해설을 제외한 실제 표시와 생성 조건을 식별함. 시도 고유번호는 기존 event_id를 사용함."""
    from learning_data.collection import digest
    return digest({"generation": {key: part for key, part in value.items() if key != "instance_id"},
                   "display": {key: display[key] for key in DISPLAY_FIELDS if key in display}})


def capture(source, item, display):
    """params 전체의 복사를 막고 출제자가 display_params로 선언한 키만 보존함."""
    validate_declaration(source)
    names = source.get("display_params")
    params = item.get("params") or {}
    if names is not None and (not isinstance(names, (list, tuple)) or
                              any(not isinstance(name, str) or name not in params for name in names)):
        raise ValueError("display_params에 선언한 키가 생성기의 params에 있는지 확인해 주세요.")
    # Python 튜플도 전송·저장될 JSON 배열로 먼저 맞추고 원래 문항은 보존함.
    try:
        selected = json.loads(json.dumps({name: params[name] for name in names}, allow_nan=False)) if names is not None else {}
    except (TypeError, ValueError) as error:
        raise ValueError("표시 조건에는 JSON으로 저장할 수 있는 안전한 값을 넣어 주세요.") from error
    value = {key: copy.deepcopy(part) for key, part in source.items() if key != "display_params"}
    value.update(version=VERSION, seed=item["seed"],
                 params=selected,
                 params_status="declared" if names is not None else "undeclared")
    value["instance_id"] = instance_id(value, display)
    return validate(value)


def from_item(item):
    """서버·모델 자료에서 저장된 필드만 읽고 표시 내용과 식별자가 같은지 확인함."""
    value = item.get("generation")
    if value is None:
        return None
    value = validate(value)
    if item.get("card") != value["generator_id"] or value["instance_id"] != instance_id(value, item):
        raise ValueError("생성 문항의 ID와 실제 표시 조건이 다릅니다.")
    if "seed" in item and (type(item["seed"]) is not int or item["seed"] != value["seed"]):
        raise ValueError("문항 시드와 생성 시드가 다릅니다.")
    return value
