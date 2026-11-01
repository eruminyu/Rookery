"""
Rookery: YouTube 쿠키 변환 · 브라우저 로그인 · 재생 제한 판별 모듈.

지원하는 쿠키 등록 방식:
1. 로컬 브라우저(Chrome/Edge/Brave) 로그인 창을 띄워 CDP로 쿠키 자동 추출
2. 브라우저 개발자 도구(F12)의 Copy as cURL / Cookie 헤더 / Netscape 텍스트 붙여넣기 변환
3. Netscape 형식 cookies.txt 파일 업로드
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import websockets

from app.core.config import get_settings, resolve_data_dir
from app.core.logger import logger

_SID_COOKIE_NAMES = ("SAPISID", "__Secure-1PAPISID", "__Secure-3PAPISID")

_YOUTUBE_LOGIN_URL = (
    "https://accounts.google.com/ServiceLogin"
    "?service=youtube&continue=https%3A%2F%2Fwww.youtube.com%2F"
)


def is_youtube_url(url: str) -> bool:
    """YouTube 동영상/라이브/단축 URL인지 확인한다."""
    lower = url.lower()
    return "youtube.com/" in lower or "youtu.be/" in lower


def youtube_cookie_file() -> Optional[str]:
    """.env에 지정한 유튜브 쿠키 파일 경로. 지정하지 않았거나 파일이 없으면 None."""
    path = getattr(get_settings(), "youtube_cookie_file", None)
    if not path:
        return None
    if not Path(path).is_file():
        logger.warning(f"YouTube 쿠키 파일을 찾을 수 없습니다: {path}")
        return None
    return path


def _unescape_cmd_caret(text: str) -> str:
    """Windows cmd의 Copy as cURL (cmd) 줄바꿈 및 캐럿(^) 이스케이프를 해제한다."""
    text = re.sub(r"\^\r?\n\s*", " ", text)
    return re.sub(r"\^(.)", r"\1", text)


def _extract_cookie_header_from_curl(text: str) -> Optional[str]:
    """cURL 명령어 문자열에서 Cookie 헤더 또는 -b 옵션 값을 추출한다."""
    cleaned = _unescape_cmd_caret(text) if '^"' in text or "^\n" in text or "^\r\n" in text else text

    # 1) -b '...' 또는 -b "..." 또는 --cookie '...'
    b_match = re.search(
        r"""(?:^|\s)(?:-b|--cookie)\s+(?:'([^']+)'|"([^"]+)")""",
        cleaned,
    )
    if b_match:
        return b_match.group(1) or b_match.group(2)

    # 2) -H 'cookie: ...' 또는 -H "cookie: ..."
    h_match = re.search(
        r"""(?:-H|--header)\s+(?:'cookie:\s*([^']+)'|"cookie:\s*([^"]+)")""",
        cleaned,
        re.IGNORECASE,
    )
    if h_match:
        return h_match.group(1) or h_match.group(2)

    return None


def _parse_netscape_cookies(text: str) -> list[tuple[str, str]]:
    """Netscape 쿠키 텍스트에서 (name, value) 목록을 추출한다."""
    pairs: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            else:
                continue
        parts = line.split("\t")
        if len(parts) >= 7:
            pairs.append((parts[5].strip(), parts[6].strip()))
    return pairs


def _validate_auth_cookie_names(cookie_names: set[str]) -> None:
    """yt-dlp가 로그인 상태로 인식하기 위한 필수 유튜브 쿠키가 있는지 검증한다."""
    has_login_info = "LOGIN_INFO" in cookie_names
    has_sid = any(name in cookie_names for name in _SID_COOKIE_NAMES)
    if not (has_login_info and has_sid):
        raise ValueError(
            "유튜브 로그인 세션 쿠키(LOGIN_INFO, SAPISID)가 포함되어 있지 않습니다. "
            "유튜브에 로그인된 상태에서 추출하거나 복사해 주세요."
        )


def convert_to_netscape_cookies(raw_text: str) -> str:
    """Netscape 텍스트, Copy as cURL(bash/cmd), 또는 Cookie 헤더 문자열을
    유효한 Netscape HTTP Cookie File 형식으로 변환하고 인증 쿠키 유무를 검증한다.
    """
    text = raw_text.strip()
    if not text:
        raise ValueError("쿠키 내용이 비어 있습니다.")

    # 1. 이미 Netscape 포맷(탭 구분 7컬럼)인 경우
    netscape_pairs = _parse_netscape_cookies(text)
    if netscape_pairs:
        _validate_auth_cookie_names({k for k, _ in netscape_pairs})
        lines = ["# Netscape HTTP Cookie File"]
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("# Netscape"):
                continue
            lines.append(stripped)
        return "\n".join(lines) + "\n"

    # 2. cURL 명령어인 경우 쿠키 문자열 추출
    cookie_str: Optional[str] = None
    if text.lower().startswith("curl "):
        cookie_str = _extract_cookie_header_from_curl(text)
        if not cookie_str:
            raise ValueError(
                "cURL 명령어에서 쿠키(-b 또는 -H 'cookie: ...')를 찾을 수 없습니다."
            )
    else:
        # 3. Raw Cookie 헤더 ("Cookie: a=b; c=d" 또는 "a=b; c=d")
        cookie_str = re.sub(r"^cookie:\s*", "", text, flags=re.IGNORECASE).strip()

    pairs: list[tuple[str, str]] = []
    for part in cookie_str.split(";"):
        item = part.strip()
        if not item or "=" not in item:
            continue
        name, _, value = item.partition("=")
        name = name.strip()
        value = value.strip()
        if name:
            pairs.append((name, value))

    _validate_auth_cookie_names({k for k, _ in pairs})

    out_lines = ["# Netscape HTTP Cookie File"]
    for name, value in pairs:
        out_lines.append(f".youtube.com\tTRUE\t/\tTRUE\t0\t{name}\t{value}")
    return "\n".join(out_lines) + "\n"


def has_youtube_auth_cookies(cookies: list[dict[str, Any]]) -> bool:
    """CDP Storage.getCookies 결과에 유튜브 로그인 세션 쿠키가 모두 있는지 확인한다."""
    yt_cookie_names = {
        str(c.get("name", ""))
        for c in cookies
        if "youtube.com" in str(c.get("domain", "")).lower()
        and c.get("value")
    }
    return "LOGIN_INFO" in yt_cookie_names and any(
        sid in yt_cookie_names for sid in _SID_COOKIE_NAMES
    )


def cdp_cookies_to_netscape(cookies: list[dict[str, Any]]) -> str:
    """CDP 쿠키 딕셔너리 목록에서 youtube.com/google.com 쿠키를 Netscape 형식으로 변환한다."""
    out_lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        domain = str(c.get("domain", "")).strip()
        lower_domain = domain.lower()
        if not (lower_domain.endswith("youtube.com") or lower_domain.endswith("google.com")):
            continue
        name = str(c.get("name", "")).strip()
        value = str(c.get("value", "")).strip()
        if not name:
            continue
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        path = str(c.get("path") or "/")
        secure = "TRUE" if c.get("secure") else "FALSE"
        expires_raw = c.get("expires", 0)
        try:
            expires = max(0, int(float(expires_raw)))
        except (TypeError, ValueError):
            expires = 0
        out_lines.append(
            f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}"
        )
    return "\n".join(out_lines) + "\n"


def find_local_chromium_browser() -> Optional[str]:
    """시스템에 설치된 Chromium 계열 브라우저(Chrome, Edge, Brave) 실행 파일 경로를 찾는다."""
    if sys.platform != "win32" and sys.platform != "darwin":
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return None

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.join(local_app_data, r"Google\Chrome\Application\chrome.exe") if local_app_data else "",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        ]
        for path in candidates:
            if path and Path(path).is_file():
                return path

    for binary in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge", "brave-browser", "chrome", "msedge"):
        found = shutil.which(binary)
        if found:
            return found

    return None


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def login_youtube_via_browser(timeout_seconds: float = 180.0) -> str:
    """로컬 Chrome/Edge 브라우저 창을 띄워 사용자가 유튜브 로그인을 완료하면
    CDP(Storage.getCookies)로 쿠키를 자동 추출해 Netscape 텍스트로 반환한다.
    """
    browser_path = find_local_chromium_browser()
    if not browser_path:
        raise RuntimeError(
            "브라우저 창을 띄울 수 있는 데스크톱 환경(Chrome/Edge)을 찾을 수 없습니다. "
            "Linux 서버 환경에서는 아래의 'cURL/쿠키 붙여넣기' 또는 '파일 업로드'를 이용해 주세요."
        )

    profile_dir = resolve_data_dir() / "yt_browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    port = _pick_free_port()

    proc = subprocess.Popen(
        [
            browser_path,
            f"--user-data-dir={profile_dir}",
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--app={_YOUTUBE_LOGIN_URL}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        ws_url: Optional[str] = None
        async with httpx.AsyncClient(timeout=3.0) as client:
            for _ in range(30):
                if proc.poll() is not None:
                    raise RuntimeError("브라우저 창이 시작 직후 닫혔습니다.")
                try:
                    resp = await client.get(f"http://127.0.0.1:{port}/json/version")
                    if resp.status_code == 200:
                        ws_url = resp.json().get("webSocketDebuggerUrl")
                        if ws_url:
                            break
                except Exception:
                    pass
                await asyncio.sleep(0.3)

        if not ws_url:
            raise RuntimeError("브라우저 디버깅 포트에 연결할 수 없습니다.")

        deadline = time.monotonic() + timeout_seconds
        async with websockets.connect(ws_url) as ws:
            msg_id = 1
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError("로그인이 완료되기 전에 브라우저 창이 닫혔습니다.")

                await ws.send(json.dumps({"id": msg_id, "method": "Storage.getCookies"}))
                raw_reply = await asyncio.wait_for(ws.recv(), timeout=5.0)
                reply = json.loads(raw_reply)
                msg_id += 1

                cookies: list[dict[str, Any]] = reply.get("result", {}).get("cookies", [])
                if has_youtube_auth_cookies(cookies):
                    # 리다이렉트 직후 후속 쿠키(__Secure-1PSIDTS 등)가 모두 기록되도록 잠시 대기
                    await asyncio.sleep(1.0)
                    await ws.send(json.dumps({"id": msg_id, "method": "Storage.getCookies"}))
                    final_reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
                    final_cookies = final_reply.get("result", {}).get("cookies", cookies)
                    netscape = cdp_cookies_to_netscape(final_cookies)
                    try:
                        await ws.send(json.dumps({"id": msg_id + 1, "method": "Browser.close"}))
                    except Exception:
                        pass
                    return netscape

                await asyncio.sleep(1.2)

        raise TimeoutError("유튜브 로그인 대기 시간(3분)이 초과되었습니다.")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()


def explain_youtube_unplayable(error: str, has_cookies: bool) -> Optional[str]:
    """유튜브 성인 인증(연령 제한) 또는 멤버십 전용 오류처럼 재시도해도 결과가 같은
    오류라면 한국어 안내 문구를 반환한다.
    """
    lower = error.lower()
    if "sign in to confirm your age" in lower or "inappropriate for some users" in lower:
        if has_cookies:
            return (
                "성인 인증(연령 확인)이 필요한 유튜브 영상입니다. "
                "등록된 유튜브 쿠키가 만료되었거나 성인 인증이 완료되지 않은 계정인지 확인해 주세요."
            )
        return (
            "성인 인증(연령 확인)이 필요한 유튜브 영상입니다. "
            "[설정 → 인증] 탭에서 유튜브 로그인을 진행하거나 쿠키를 등록해 주세요."
        )

    if "members-only" in lower or "join this channel to get access" in lower:
        if has_cookies:
            return (
                "채널 멤버십(구독자) 전용 유튜브 영상입니다. "
                "해당 채널 멤버십에 가입된 계정의 유튜브 쿠키인지 확인해 주세요."
            )
        return (
            "채널 멤버십(구독자) 전용 유튜브 영상입니다. "
            "[설정 → 인증] 탭에서 멤버십 가입 계정의 유튜브 쿠키를 등록해 주세요."
        )

    return None
