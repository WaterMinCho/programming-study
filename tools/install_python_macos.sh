#!/bin/sh
# Python이 없는 Mac에 공식 설치 파일을 확인한 뒤 설치함.
install_locked() (
    umask 077
    version=3.14.10
    expected=286c7018aa2730f6747ca433dccdc2b31be45f078a9ea0ffa44d5f06368fd2d7
    url="https://www.python.org/ftp/python/$version/python-$version-macos11.pkg"
    runtime=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14
    base="$HOME/.rokey-study"
    temporary=
    trap '[ -z "$temporary" ] || /bin/rm -rf "$temporary"' EXIT
    trap 'exit 130' HUP INT TERM
    pending="$base/python-certificates.pending"
    had_pending=no
    [ ! -f "$pending" ] || had_pending=yes
    # 앞서 열린 다른 창에서 설치를 끝냈으면 다시 설치하지 않음.
    if [ -x "$runtime" ] && [ ! -f "$pending" ]; then
        "$runtime" -c 'import ssl, venv' && return 0
    fi
    temporary=$(/usr/bin/mktemp -d "$base/python-download.XXXXXX") || return 1
    package=
    choices=
    repair_only=no
    if [ "$had_pending" = yes ] && [ -x "$runtime" ] && "$runtime" -c 'import ssl, venv'; then
        repair_only=yes
    fi
    if [ "$repair_only" != yes ]; then
    package="$temporary/python.pkg"
    printf '\nPython 설치 파일을 내려받고 있습니다.\n'
    /usr/bin/curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 \
        --connect-timeout 20 --max-time 600 --output "$package" "$url" || {
        printf '내려받지 못했습니다. 인터넷 연결을 확인한 뒤 다시 실행해 주세요.\n'
        return 1
    }
    actual=$(/usr/bin/shasum -a 256 "$package") || return 1
    if [ "${actual%% *}" != "$expected" ]; then
        printf '설치 파일이 공식 파일과 일치하지 않아 중단했습니다. 다시 실행해 주세요.\n'
        return 1
    fi
    signature=$(/usr/sbin/pkgutil --check-signature "$package") || return 1
    case "$signature" in
        *'Developer ID Installer: Python Software Foundation (BMM5U3QVKW)'*) ;;
        *) printf 'Python 설치 파일의 서명을 확인하지 못했습니다.\n'; return 1 ;;
    esac
    choices="$temporary/choices.plist"
    /bin/cat > "$choices" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><array>
<dict><key>choiceIdentifier</key><string>org.python.Python.PythonUnixTools-3.14</string><key>choiceAttribute</key><string>selected</string><key>attributeSetting</key><integer>0</integer></dict>
<dict><key>choiceIdentifier</key><string>org.python.Python.PythonProfileChanges-3.14</string><key>choiceAttribute</key><string>selected</string><key>attributeSetting</key><integer>0</integer></dict>
<dict><key>choiceIdentifier</key><string>org.python.Python.PythonDocumentation-3.14</string><key>choiceAttribute</key><string>selected</string><key>attributeSetting</key><integer>0</integer></dict>
</array></plist>
PLIST
    fi
    : > "$pending" || return 1
    printf '관리자 확인 창에서 설치를 허용해 주세요.\n'
    # 관리자 설치가 끝나기 전에 터미널이 닫혀도 잠금을 먼저 풀지 않음.
    trap '' HUP INT TERM
    outcome=$(/usr/bin/osascript - "$package" "$choices" <<'APPLESCRIPT'
on run argv
    try
        set certificateCommand to "/bin/sh '/Applications/Python 3.14/Install Certificates.command'"
        set commandText to "umask 022; " & certificateCommand
        if (item 1 of argv) is not "" then
            set commandText to "umask 022; /usr/sbin/installer -pkg " & quoted form of (item 1 of argv) & " -applyChoiceChangesXML " & quoted form of (item 2 of argv) & " -target / && " & certificateCommand
        end if
        do shell script commandText with administrator privileges
        return "installed"
    on error messageText number errorNumber
        if errorNumber is -128 then return "cancelled"
        error messageText number errorNumber
    end try
end run
APPLESCRIPT
    )
    status=$?
    trap 'exit 130' HUP INT TERM
    if [ "$outcome" = cancelled ]; then
        [ "$had_pending" = yes ] || /bin/rm -f "$pending"
        return 2
    fi
    if [ "$status" -ne 0 ]; then
        printf '설치를 마치지 못했습니다. 취소했다면 다음 실행에서 다시 설치할 수 있습니다.\n'
        return "$status"
    fi
    "$runtime" -c 'import ssl, venv; print("Python 설치가 끝났습니다.")' || return 1
    /bin/rm -f "$pending"

)

install_python() {
    version=3.14.10
    printf 'Python 3.10~3.14(64비트)가 필요합니다.\n'
    printf 'python.org에서 Python %s을 받아 설치합니다.\n' "$version"
    printf 'Mac의 관리자 확인 창이 열립니다. 설치 후 PyQt6 준비를 이어갑니다.\n'
    printf '설치할까요? [y/N] '
    read -r reply || return 2
    case "$reply" in y|Y|yes|YES) ;; *) return 2 ;; esac

    base="$HOME/.rokey-study"
    /bin/mkdir -p "$base" || return 1
    /usr/bin/lockf -sk -t 0 "$base/python-install.lock" /bin/sh "$0" --locked
    status=$?
    if [ "$status" -eq 75 ]; then
        printf '다른 설치가 진행 중입니다. 설치가 끝난 뒤 다시 실행해 주세요.\n'
    fi
    return "$status"
}

case "$1" in
    --locked) install_locked ;;
    *) install_python ;;
esac
