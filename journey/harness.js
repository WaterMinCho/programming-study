// 여정 Node 하네스. 실행기가 임시 폴더에 복사해 자식 프로세스로만 띄움.
//
// node --max-old-space-size=N harness.js job.json   (작업 폴더는 케이스 폴더)
// job.json: {"source", "args", "calls", "pid", "calling", "result"}. 경로는 케이스 폴더 기준이고 args 는 절대 경로일 수 있음.
//
// 학생 코드가 같은 실행 환경에서 돌아서 JSON.stringify 같은 것을 바꿔 끼울 수 있으므로, 컴파일 전에 하네스가 쓸 함수를
// 지역 상수로 잡아 두고 인코더는 for 문과 그 함수만 씀. 호출마다 factory 를 다시 불러 최상위 상태가 다음 호출로 새지 않음.
"use strict";
const fs = require("fs");
const vm = require("vm");

const stringify = JSON.stringify;
const parse = JSON.parse;
const hrtime = process.hrtime.bigint.bind(process.hrtime);
const isSafeInteger = Number.isSafeInteger;
const isFiniteNumber = Number.isFinite;
const isArray = Array.isArray;
const getProto = Object.getPrototypeOf;
const isView = ArrayBuffer.isView;
const writeFileSync = fs.writeFileSync;
const renameSync = fs.renameSync;
const readFileSync = fs.readFileSync;
const resourceUsage = process.resourceUsage.bind(process);
const realExit = process.exit.bind(process);
const MapProto = Map.prototype;
const SetProto = Set.prototype;
const atomicsWait = Atomics.wait;
const sleepCell = new Int32Array(new SharedArrayBuffer(4));

const OUTPUT_LIMIT = 1000000;
const PRINT_KEEP = 20000;
// 반환값 배열이 겹칠 수 있는 단계. 더 깊으면 부모가 JSON 을 읽다가 스택이 넘칠 수 있음
const MAX_DEPTH = 64;
const UNDEFINED_NOTE = "undefined 를 반환했습니다. return 을 빠뜨렸는지 확인하세요.";
const HOLE_NOTE = "배열에 빈 칸이나 undefined 가 있습니다. 모든 칸을 채워 반환하세요.";
const NAN_NOTE = "NaN 이나 Infinity 는 반환할 수 없습니다.";
const BIG_NOTE = "2^53 을 넘는 정수는 Number 로 정확히 나타낼 수 없습니다.";
const BIGINT_NOTE = "BigInt 는 Number(…) 로 바꿔 반환하세요.";
const MAP_NOTE = "Map 은 반환할 수 없습니다. 배열로 바꿔 반환하세요.";
const SET_NOTE = "Set 은 반환할 수 없습니다. Array.from(...) 으로 배열로 바꿔 반환하세요.";
const TYPED_NOTE = "TypedArray 는 반환할 수 없습니다. Array.from(...) 으로 배열로 바꿔 반환하세요.";
const OBJECT_NOTE = "객체는 반환할 수 없습니다. 정수·문자열·불리언이나 그 배열로 반환하세요.";
const DEPTH_NOTE = "배열이 64겹을 넘게 겹쳐 있습니다. 반복문 안에서 answer = [answer, x] 처럼 배열을 다시 감싸고 있는지 확인하세요.";
const FUNCTION_NOTE = "함수를 반환했습니다. 값을 반환하세요.";
const PROMISE_NOTE = "Promise 를 반환했습니다. async 를 빼세요.";
const OUTPUT_NOTE = "출력이 1,000,000자를 넘었습니다.";
const EXIT_NOTE = "process.exit 는 쓸 수 없습니다.";
const ENCODE_NOTE = "반환값을 채점용 JSON 으로 바꾸지 못했습니다";
const MODULE_NOTE = "프로그래머스처럼 import/export 대신 require 를 쓰세요.";
const STACK_NOTE = "재귀가 너무 깊거나 Math.max(...arr)·arr.push(...big)처럼 큰 배열을 펼쳐 넘기면 이 오류가 납니다. "
    + "Node 는 재귀가 수천 단계, 펼침이 약 11만 개를 넘으면 멈추니 반복문으로 바꾸세요.";

// 임시 이름에 쓴 뒤 바꿔치기함. Windows 는 부모가 읽는 동안 바꿔치기가 거부되므로 harness.py 처럼 5ms 씩 쉬며 20번까지 해 봄
function writeFile(file, text) {
    const tmp = file + ".tmp";
    writeFileSync(tmp, text);
    for (let attempt = 0; ; attempt++) {
        try {
            renameSync(tmp, file);
            return;
        } catch (error) {
            if (attempt >= 19 || (error.code !== "EPERM" && error.code !== "EBUSY" && error.code !== "EACCES")) {
                throw error;
            }
            atomicsWait(sleepCell, 0, 0, 5);
        }
    }
}

// 출력 모으기. console.log 는 write 의 예외를 삼키므로 한도를 넘으면 표시만 남기고 호출이 끝난 뒤 판정함
const printed = [];
let printedSize = 0;
let outputOver = false;

function collect(chunk, encoding, callback) {
    const text = typeof chunk === "string" ? chunk : String(chunk);
    if (typeof encoding === "function") {
        callback = encoding;
    }
    printedSize += text.length;
    if (printedSize > OUTPUT_LIMIT) {
        outputOver = true;
        throw new Error(OUTPUT_NOTE);
    }
    printed.push(text);
    if (typeof callback === "function") {
        callback();
    }
    return true;
}

function printedText() {
    let text = "";
    for (let i = 0; i < printed.length; i++) {
        text += printed[i];
    }
    return text;
}

function lineOf(error) {
    const stack = error && typeof error.stack === "string" ? error.stack : "";
    const found = /solution\.js:(\d+)/.exec(stack);
    return found ? Number(found[1]) : null;
}

function errorText(error) {
    let text;
    if (error instanceof Error || (error && typeof error === "object" && typeof error.message === "string")) {
        text = (error.name || "Error") + ": " + error.message;
    } else {
        text = "Error: " + String(error);
    }
    if (text.length > 2000) {
        text = text.slice(0, 2000) + "…";
    }
    const line = lineOf(error);
    return line ? text + " (" + line + "번째 줄)" : text;
}

function isStackOverflow(error) {
    return error instanceof RangeError && typeof error.message === "string"
        && error.message.indexOf("Maximum call stack size exceeded") >= 0;
}

// 반환값 검사. 허용하지 않으면 이유를, 허용하면 빈 글을 돌려줌. depth 는 value 가 배열일 때 몇 겹째인지
function reject(value, depth) {
    if (value === null) {
        return "";
    }
    const kind = typeof value;
    if (kind === "boolean" || kind === "string") {
        return "";
    }
    if (kind === "number") {
        if (!isFiniteNumber(value)) {
            return NAN_NOTE;
        }
        if (value % 1 === 0 && !isSafeInteger(value)) {
            return BIG_NOTE;
        }
        return "";
    }
    if (kind === "undefined") {
        return HOLE_NOTE;
    }
    if (kind === "bigint") {
        return BIGINT_NOTE;
    }
    if (kind === "function") {
        return FUNCTION_NOTE;
    }
    if (isArray(value)) {
        if (depth > MAX_DEPTH) {
            return DEPTH_NOTE;
        }
        for (let i = 0; i < value.length; i++) {
            if (!(i in value)) {
                return HOLE_NOTE;
            }
            const bad = reject(value[i], depth + 1);
            if (bad) {
                return bad;
            }
        }
        return "";
    }
    const proto = getProto(value);
    if (proto === MapProto) {
        return MAP_NOTE;
    }
    if (proto === SetProto) {
        return SET_NOTE;
    }
    if (isView(value)) {
        return TYPED_NOTE;
    }
    return OBJECT_NOTE;
}

function encode(value) {
    if (value === undefined) {
        return {text: null, note: UNDEFINED_NOTE};
    }
    if (value !== null && (typeof value === "object" || typeof value === "function") && typeof value.then === "function") {
        return {text: null, note: PROMISE_NOTE};
    }
    const bad = reject(value, 1);
    if (bad) {
        return {text: null, note: bad};
    }
    return {text: stringify(value), note: ""};
}

function main(jobPath) {
    const job = parse(readFileSync(jobPath, "utf8"));
    writeFile(job.pid, String(process.pid));
    const result = {status: "done", values: [], times_ns: [], peak: 0, printed: "", printed_cut: false,
        error: "", note: "", fatal: null, failed_call: null};

    function finish() {
        result.peak = resourceUsage().maxRSS * 1024;
        const text = printedText();
        if (text.length > PRINT_KEEP) {
            result.printed = text.slice(0, PRINT_KEEP);
            result.printed_cut = true;
        } else {
            result.printed = text;
        }
        writeFile(job.result, stringify(result));
        realExit(0);
    }

    process.stdout.write = collect;
    process.stderr.write = collect;
    console.log("");
    printed.length = 0;
    printedSize = 0;
    process.exit = function () {
        throw new Error(EXIT_NOTE);
    };

    const source = readFileSync(job.source, "utf8");
    let factory;
    try {
        factory = vm.compileFunction(source + "\n;return typeof solution === 'function' ? solution : undefined;",
            ["require", "module", "exports", "__filename", "__dirname"], {filename: "solution.js"});
    } catch (error) {
        const message = (error && error.name ? error.name : "SyntaxError") + ": " + (error && error.message ? error.message : String(error));
        result.status = "fatal";
        result.fatal = {kind: "syntax", message: message, line: lineOf(error)};
        if (/Unexpected token 'export'|Cannot use import statement/.test(message)) {
            result.note = MODULE_NOTE;
        }
        finish();
    }

    const allArgs = parse(readFileSync(job.args, "utf8"));

    function fail(k, status, error, note) {
        result.status = status;
        result.failed_call = k;
        result.error = errorText(error);
        result.note = note || "";
    }

    for (let k = 0; k < allArgs.length; k++) {
        writeFile(job.calling, "load " + k);
        const mod = {exports: {}};
        let solution;
        try {
            solution = factory(require, mod, mod.exports, "solution.js", ".");
        } catch (error) {
            const note = isStackOverflow(error) ? STACK_NOTE : (outputOver ? OUTPUT_NOTE : "");
            if (k === 0) {
                result.status = "fatal";
                result.fatal = {kind: "load", message: errorText(error).replace(/ \(\d+번째 줄\)$/, ""), line: lineOf(error)};
                result.note = note;
            } else {
                fail(k, "runtime", error, note);
            }
            break;
        }
        if (typeof solution !== "function") {
            result.status = "fatal";
            result.fatal = {kind: "no_solution", message: "solution 함수가 없습니다.", line: null};
            break;
        }
        writeFile(job.calling, "call " + k);
        let value;
        const t0 = hrtime();
        let t1;
        try {
            value = solution.apply(undefined, allArgs[k]);
            t1 = hrtime();
        } catch (error) {
            result.times_ns.push(Number(hrtime() - t0));
            if (outputOver) {
                fail(k, "runtime", new Error(OUTPUT_NOTE), OUTPUT_NOTE);
            } else {
                fail(k, "runtime", error, isStackOverflow(error) ? STACK_NOTE : "");
            }
            break;
        }
        result.times_ns.push(Number(t1 - t0));
        if (outputOver) {
            fail(k, "runtime", new Error(OUTPUT_NOTE), OUTPUT_NOTE);
            break;
        }
        let encoded;
        try {
            encoded = encode(value);
        } catch (error) {
            // 읽을 때 예외를 내는 Proxy·getter
            let message = errorText(error);
            if (message.length > 300) {
                message = message.slice(0, 300) + "…";
            }
            encoded = {text: null, note: ENCODE_NOTE + "(" + message + ")."};
        }
        if (encoded.text === null) {
            result.status = "bad_return";
            result.failed_call = k;
            result.note = encoded.note;
            break;
        }
        result.values.push(encoded.text);
    }
    finish();
}

main(process.argv[2]);
