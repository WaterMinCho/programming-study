"""공개 동영상 식별자만 담은 재생 문서와 주소 검사를 제공함."""
from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, urlencode, urlsplit

# gui.icon.APP_ID와 같은 설치 식별자를 사용함. 실제 웹사이트 주소로 접속하지 않음.
APP_ID = "rokey.python.study"
APP_ORIGIN = "https://" + APP_ID
EMBED_HOST = "www.youtube-nocookie.com"
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")


def checked_video_id(value):
    if not isinstance(value, str) or not VIDEO_ID.fullmatch(value):
        raise ValueError("영상 주소를 확인하지 못했습니다.")
    return value


def watch_url(video_id):
    return "https://www.youtube.com/watch?v=" + checked_video_id(video_id)


def embed_url(video_id):
    query = urlencode({"enablejsapi": 1, "autoplay": 0, "controls": 1, "fs": 1,
                       "playsinline": 1, "hl": "ko", "cc_lang_pref": "ko", "origin": APP_ORIGIN})
    return f"https://{EMBED_HOST}/embed/{checked_video_id(video_id)}?{query}"


def _https_parts(url):
    try:
        parts = urlsplit(url)
        if parts.scheme == "https" and not parts.username and not parts.password and parts.port in (None, 443):
            return parts
    except (ValueError, TypeError):
        pass
    return None


def is_embed_url(url, video_id):
    parts = _https_parts(url)
    return bool(parts and parts.hostname == EMBED_HOST and parts.path == "/embed/" + checked_video_id(video_id))


def is_playback_frame(url, video_id):
    """플레이어의 HTTPS 하위 프레임을 허용하며 광고 리소스를 골라 차단하지 않음."""
    if url in ("about:blank", "about:srcdoc"):
        return True
    parts = _https_parts(url)
    if not parts or not parts.hostname or parts.hostname.startswith("accounts."):
        return False
    if parts.hostname in (EMBED_HOST, "www.youtube.com", "youtube.com"):
        if parts.path.startswith("/embed/"):
            return is_embed_url(url, video_id)
        if parts.path in ("/watch", "/signin"):
            return False
    return True


def external_video_link(url):
    """사용자가 누른 공식 영상·채널 주소만 외부로 넘길 수 있게 검사함."""
    parts = _https_parts(url)
    if not parts or len(url) > 2048:
        return False
    if parts.hostname == "youtu.be":
        return bool(VIDEO_ID.fullmatch(parts.path.lstrip("/")))
    if parts.hostname not in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        return False
    if parts.path == "/watch":
        return bool(VIDEO_ID.fullmatch(parse_qs(parts.query).get("v", [""])[0]))
    return bool(re.fullmatch(r"/(?:shorts/[A-Za-z0-9_-]{11}|channel/[A-Za-z0-9_-]+|@[\w.-]+)", parts.path))


ERROR_MESSAGES = {
    2: "영상 주소를 확인하지 못했습니다. YouTube에서 열어 주세요.",
    5: "이 환경에서는 영상을 재생하지 못했습니다. YouTube에서 열어 주세요.",
    100: "영상이 삭제되었거나 비공개로 바뀌었습니다. YouTube에서 확인해 주세요.",
    101: "이 영상은 앱 안에서 재생할 수 없습니다. YouTube에서 열어 주세요.",
    150: "이 영상은 앱 안에서 재생할 수 없습니다. YouTube에서 열어 주세요.",
    153: "YouTube가 앱 식별 정보를 확인하지 못했습니다. YouTube에서 열어 주세요.",
}


def error_message(code):
    return ERROR_MESSAGES.get(code, "영상을 불러오지 못했습니다. 연결을 확인하거나 YouTube에서 열어 주세요.")


def player_html(video_id):
    """개인 기록·제목·개인 URL을 받지 않으며 공식 조작부를 가리지 않음."""
    source = html.escape(embed_url(video_id), quote=True)
    return '''<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' https://www.youtube.com https://s.ytimg.com; style-src 'unsafe-inline'; frame-src https://www.youtube-nocookie.com">
<style>html,body{margin:0;width:100%;height:100%;background:#000}iframe{border:0;width:100%;height:100%;min-width:200px;min-height:200px;display:block}</style>
</head><body>
<iframe id="player" title="YouTube 영상 재생" src="''' + source + '''" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>
<script>
window.rokeyState = {kind: "requesting"};
let player = null;
let disposed = false;
let ready = false;
let attempted = false;
let initial = true;
// Qt에서 선택한 영상이 절반 넘게 보일 때만 한 번 요청함.
// https://developers.google.com/youtube/terms/required-minimum-functionality
window.tryRokeyPlayback = function(visible) {
    if (visible && !document.hidden && ready && !attempted && !disposed && window.rokeyState.kind !== "error") {
        attempted = true;
        player.playVideo();
    }
};
function report(kind, code) {
    if (!disposed && window.rokeyState.kind !== "error") window.rokeyState = {kind: kind, code: code, initial: initial};
}
function onYouTubeIframeAPIReady() {
    if (disposed) return;
    player = new YT.Player("player", {events: {
        onReady: () => { ready = true; report("ready"); },
        onStateChange: e => {
            if ([0, 1, 2].includes(e.data)) initial = false;
            if ([0, 1, 2, 3].includes(e.data)) attempted = true;
            report("state", e.data);
        },
        onError: e => report("error", e.data),
        onAutoplayBlocked: () => { initial = false; attempted = true; report("blocked"); }
    }});
}
window.stopRokeyVideo = function() {
    disposed = true;
    if (player) { try { player.stopVideo(); } finally { player.destroy(); player = null; } }
};
window.addEventListener("pagehide", window.stopRokeyVideo);
const api = document.createElement("script");
api.src = "https://www.youtube.com/iframe_api";
api.onerror = () => report("error", 0);
document.head.appendChild(api);
</script></body></html>'''
