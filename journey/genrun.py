# -*- coding: utf-8 -*-
"""생성기 실행용 자식 스크립트. 부모(runner.generate_to)가 띄우고, 저장소에서는 journey.gen 만 import 함.

python -S -B -X utf8 genrun.py 저장소루트 gen.py사본 명세.json 출력경로 [--validate validate.py사본]

명세는 {"gen": 함수 이름, "seed": 정수, "params": {...}, "count": 정수 | null} 이고, 결과 파일은 [[인자…], …] 임.
묶음(count)은 Rng(seed) 하나로 count 번 연달아 부름. --validate 를 주면 입력마다 validate(*args) 를 부르고 처음 어긴 것을
{"invalid": {"index", "message"} | null} 로 표준 출력에 찍음. -I 를 쓰지 않아 스크립트 폴더가 sys.path[0] 에 들어오므로
맨 먼저 그 자리를 저장소 루트로 바꿈(부모가 PYTHONHASHSEED=0 을 줌).
"""
import json
import os
import sys


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_function(path, name):
    namespace = {"__name__": os.path.splitext(os.path.basename(path))[0]}
    exec(compile(read(path), os.path.basename(path), "exec"), namespace)
    function = namespace.get(name)
    if not callable(function):
        raise SystemExit("%s 에 %s 함수가 없습니다." % (os.path.basename(path), name))
    return function


def main(argv):
    root, gen_path, spec_path, out_path = argv[:4]
    validate_path = None
    if len(argv) >= 6 and argv[4] == "--validate":
        validate_path = argv[5]
    sys.path[0] = root
    from journey.gen import Rng

    spec = json.loads(read(spec_path))
    generate = load_function(gen_path, spec["gen"])
    rng = Rng(spec["seed"])
    params = spec.get("params") or {}
    count = spec.get("count") or 1
    inputs = []
    for _ in range(count):
        inputs.append(list(generate(rng, **params)))

    invalid = None
    if validate_path:
        validate = load_function(validate_path, "validate")
        for index, args in enumerate(inputs):
            message = validate(*args)
            if message:
                invalid = {"index": index, "message": message}
                break

    tmp = "%s.tmp%d" % (out_path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(inputs, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out_path)
    if validate_path:
        sys.stdout.write(json.dumps({"invalid": invalid}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
