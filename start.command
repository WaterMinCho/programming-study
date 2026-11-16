#!/bin/sh
# macOS 첫 실행. 오류가 나면 안내를 읽을 때까지 터미널을 유지함.
launch_log="$HOME/.rokey-study/launch.log"
if (umask 077; /bin/mkdir -p "$HOME/.rokey-study" && : >> "$launch_log") 2>/dev/null; then
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
            if [ -n "$launch_python" ]; then
                "$launch_python" -c 'import termios; termios.tcflush(0, termios.TCIFLUSH)' 2>/dev/null
            fi
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
    "$1" -c 'import sys; ok = (3, 10) <= sys.version_info[:2] <= (3, 14) and sys.maxsize > 2**32; sys.exit(0 if ok else 3)' </dev/null >/dev/null 2>&1
    case $? in
        0) launch_python=$1; return 0 ;;
        3) [ -n "$launch_fallback" ] || launch_fallback=$1 ;;
    esac
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
    launch_fallback=
    # 설치한 Python이 PATH에서 빠져도 기존 전용 환경을 찾을 수 있게 함.
    try_python "$(command -v python3)" || {
        for minor in 14 13 12 11 10; do
            try_python "$(command -v "python3.$minor")" && break
            for prefix in /Library/Frameworks/Python.framework/Versions/3.$minor/bin /opt/homebrew/bin /usr/local/bin; do
                try_python "$prefix/python3.$minor" && break 2
            done
        done
    }
    # 이미 쓸 수 있는 PyQt6·전용 환경은 bootstrap이 먼저 확인함.
    if [ -z "$launch_python" ]; then
        existing="${STUDY_VENV:-$HOME/.rokey-study/venv}/bin/python"
        if [ -x "$existing" ] && "$existing" -c 'import PyQt6.QtWidgets' >/dev/null 2>&1; then
            try_python "$existing" || :
        fi
        if [ -z "$launch_python" ] && [ -n "$launch_fallback" ] &&
            "$launch_fallback" -c 'import PyQt6.QtWidgets' >/dev/null 2>&1; then
            launch_python=$launch_fallback
        fi
    fi
    if [ -z "$launch_python" ] || [ -f "$HOME/.rokey-study/python-certificates.pending" ]; then
        /bin/sh tools/install_python_macos.sh
        install_status=$?
        if [ "$install_status" -eq 2 ]; then
            printf '설치를 취소했습니다. 다음 실행에서 다시 설치할 수 있습니다.\n'
            [ -n "$launch_python" ] || finish 0
        elif [ "$install_status" -ne 0 ]; then
            [ -n "$launch_python" ] || finish "$install_status"
            printf 'Python 준비를 마치지 못했습니다. 기존 실행 환경으로 프로그램을 엽니다.\n'
        fi
        if [ -z "$launch_python" ]; then
            try_python /Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 || finish 1
        fi
    fi

    record "start.command Python=$launch_python"
    printf '프로그램을 시작합니다. 설치 안내나 오류는 이 터미널에 표시됩니다.\n'
    "$launch_python" -u study.py "$@"
    finish $?
}

launch "$@"
