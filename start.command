#!/bin/sh
# macOS 첫 실행. 오류가 나면 안내를 읽을 때까지 터미널을 유지함.
umask 077
launch_log="$HOME/.rokey-study/launch.log"
if /bin/mkdir -p "$HOME/.rokey-study" && : >> "$launch_log"; then
    /bin/chmod 600 "$launch_log"
else
    launch_log=/dev/null
fi

record() {
    printf '%s %s\n' "$(/bin/date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$launch_log"
}

finish() {
    launch_status=$1
    record "start.command exit=$launch_status"
    if [ "$launch_status" -ne 0 ] && [ "$launch_status" -ne 130 ]; then
        printf '\n프로그램을 열지 못했습니다. 위의 오류 내용을 확인해 주세요.\n'
        printf '다시 실행: ./start.command\n'
        if [ "$launch_log" != /dev/null ]; then
            printf '실행 기록: %s (Python 경로와 종료 코드)\n' "$launch_log"
        fi
        if [ -t 0 ]; then
            printf '\n오류 화면을 복사한 뒤 Enter를 누르면 종료합니다. '
            read -r launch_reply
        fi
    fi
    exit "$launch_status"
}

try_python() {
    [ -n "$1" ] && [ -x "$1" ] || return 1
    # 개발 도구가 없는 맥의 python3는 설치 창을 여는 스텁일 수 있음.
    if [ "$1" = /usr/bin/python3 ] && ! /usr/bin/xcode-select -p >/dev/null 2>&1; then
        return 1
    fi
    if "$1" -c 'import sys; sys.exit(not ((3, 10) <= sys.version_info[:2] <= (3, 14) and sys.maxsize > 2**32))' </dev/null >/dev/null 2>&1; then
        launch_python=$1
        return 0
    fi
    record "Python unavailable or unsupported: $1"
    return 1
}

launch() {
    cd "$(dirname "$0")" || finish 1
    if [ ! -f study.py ] || [ ! -f bootstrap.py ]; then
        printf '프로그램 파일을 찾지 못했습니다. 저장소 폴더 안의 start.command를 열어주세요.\n'
        finish 1
    fi

    launch_python=
    try_python "$(command -v python3)" || {
        for minor in 14 13 12 11 10; do
            try_python "$(command -v "python3.$minor")" && break
            for prefix in /Library/Frameworks/Python.framework/Versions/3.$minor/bin /opt/homebrew/bin /usr/local/bin; do
                try_python "$prefix/python3.$minor" && break 2
            done
        done
    }
    if [ -z "$launch_python" ]; then
        printf 'Python 3.10~3.14(64비트)를 찾지 못했습니다.\n'
        printf 'https://www.python.org/downloads/latest/python3.14/ 에서 macOS 설치 파일을 받아 설치해 주세요.\n'
        printf '설치 후 이 start.command 파일을 다시 열어주세요.\n'
        finish 1
    fi

    record "start.command Python=$launch_python"
    printf '프로그램을 시작합니다. 설치 안내나 오류는 이 터미널에 표시됩니다.\n'
    "$launch_python" -u study.py "$@"
    finish $?
}

launch "$@"
