"""유튜브 쿠키 변환·파일 대여·브라우저 로그인·연령 제한 즉시 실패 테스트."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.engine.youtube_cookies import (
    cdp_cookies_to_netscape,
    convert_to_netscape_cookies,
    explain_youtube_unplayable,
    has_youtube_auth_cookies,
    is_youtube_url,
)
from app.engine.twitcasting import borrow_cookie_file


def test_is_youtube_url() -> None:
    assert is_youtube_url("https://www.youtube.com/watch?v=IS_NM8c020w")
    assert is_youtube_url("https://youtu.be/IS_NM8c020w")
    assert is_youtube_url("https://m.youtube.com/watch?v=IS_NM8c020w")
    assert not is_youtube_url("https://chzzk.naver.com/live/abc")
    assert not is_youtube_url("https://twitcasting.tv/user")


def test_convert_netscape_format_passthrough() -> None:
    raw = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1800000000\tLOGIN_INFO\tAFmmF2swRQIh\n"
        ".youtube.com\tTRUE\t/\tTRUE\t1800000000\tSAPISID\tabcd1234/efgh5678\n"
    )
    out = convert_to_netscape_cookies(raw)
    assert out.startswith("# Netscape HTTP Cookie File")
    assert "LOGIN_INFO\tAFmmF2swRQIh" in out
    assert "SAPISID\tabcd1234/efgh5678" in out


def test_convert_curl_bash_to_netscape() -> None:
    curl_cmd = (
        "curl 'https://www.youtube.com/watch?v=IS_NM8c020w' \\\n"
        "  -H 'accept: text/html' \\\n"
        "  -b 'VISITOR_INFO1_LIVE=xyz; LOGIN_INFO=login_tok; SAPISID=sapi_val; __Secure-1PSID=sec1' \\\n"
        "  -H 'user-agent: Mozilla/5.0'"
    )
    out = convert_to_netscape_cookies(curl_cmd)
    assert out.startswith("# Netscape HTTP Cookie File")
    assert ".youtube.com\tTRUE\t/\tTRUE\t0\tLOGIN_INFO\tlogin_tok" in out
    assert ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tsapi_val" in out
    assert ".youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-1PSID\tsec1" in out


def test_convert_curl_cmd_windows_to_netscape() -> None:
    curl_cmd = (
        'curl ^"https://www.youtube.com/^" ^\r\n'
        '  -H ^"cookie: LOGIN_INFO=win_login; __Secure-3PAPISID=win_3p; SID=sid_val^"'
    )
    out = convert_to_netscape_cookies(curl_cmd)
    assert "LOGIN_INFO\twin_login" in out
    assert "__Secure-3PAPISID\twin_3p" in out
    assert "SID\tsid_val" in out


def test_convert_raw_cookie_header_to_netscape() -> None:
    raw = "Cookie: LOGIN_INFO=raw_login; SAPISID=raw_sapi; HSID=hsid_val"
    out = convert_to_netscape_cookies(raw)
    assert "LOGIN_INFO\traw_login" in out
    assert "SAPISID\traw_sapi" in out
    assert "HSID\thsid_val" in out


def test_convert_rejects_missing_auth_cookies() -> None:
    with pytest.raises(ValueError, match="LOGIN_INFO"):
        convert_to_netscape_cookies("VISITOR_INFO1_LIVE=only_visitor; YSC=123")


def test_has_youtube_auth_cookies_and_cdp_conversion() -> None:
    cdp_cookies = [
        {"domain": ".youtube.com", "path": "/", "secure": True, "expires": 1800000000, "name": "LOGIN_INFO", "value": "tok"},
        {"domain": ".youtube.com", "path": "/", "secure": True, "expires": 1800000000, "name": "__Secure-3PAPISID", "value": "3p_val"},
        {"domain": ".google.com", "path": "/", "secure": True, "expires": 1800000000, "name": "SID", "value": "g_sid"},
        {"domain": "example.com", "path": "/", "secure": False, "expires": 0, "name": "OTHER", "value": "ignore"},
    ]
    assert has_youtube_auth_cookies(cdp_cookies) is True
    netscape = cdp_cookies_to_netscape(cdp_cookies)
    assert "LOGIN_INFO\ttok" in netscape
    assert "__Secure-3PAPISID\t3p_val" in netscape
    assert ".google.com\tTRUE\t/\tTRUE\t1800000000\tSID\tg_sid" in netscape
    assert "example.com" not in netscape


def test_borrow_cookie_file_lends_youtube_cookie_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yt_cookie = tmp_path / "youtube_cookies.txt"
    yt_cookie.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tLOGIN_INFO\tabc\n", encoding="utf-8")

    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "youtube_cookie_file", str(yt_cookie))

    with borrow_cookie_file("https://www.youtube.com/watch?v=IS_NM8c020w") as borrowed:
        assert borrowed is not None
        assert borrowed != str(yt_cookie)
        assert Path(borrowed).is_file()
        Path(borrowed).write_text("modified by yt-dlp", encoding="utf-8")

    # 임시 사본은 삭제되고 원본은 보존되어야 한다.
    assert not Path(borrowed).exists()
    assert "LOGIN_INFO" in yt_cookie.read_text(encoding="utf-8")


def test_explain_youtube_unplayable_age_restricted() -> None:
    err = "ERROR: [youtube] IS_NM8c020w: Sign in to confirm your age. This video may be inappropriate for some users."
    msg_no_cookie = explain_youtube_unplayable(err, has_cookies=False)
    assert msg_no_cookie is not None
    assert "성인 인증" in msg_no_cookie or "연령" in msg_no_cookie

    msg_with_cookie = explain_youtube_unplayable(err, has_cookies=True)
    assert msg_with_cookie is not None
    assert "만료" in msg_with_cookie


def test_youtube_cookie_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import app
    import app.api.platforms as platforms_mod

    fake_cookie_path = tmp_path / "youtube_cookies.txt"
    monkeypatch.setattr(platforms_mod, "_YOUTUBE_COOKIE_SAVE_PATH", fake_cookie_path)
    monkeypatch.setattr(platforms_mod, "_update_env_file", lambda updates: None)

    client = TestClient(app)

    # 1. 텍스트(cURL/Cookie) 저장 엔드포인트
    resp = client.post(
        "/api/platforms/youtube/cookie-text",
        json={"text": "Cookie: LOGIN_INFO=my_login; SAPISID=my_sapi"},
    )
    assert resp.status_code == 200
    assert fake_cookie_path.is_file()
    assert "LOGIN_INFO\tmy_login" in fake_cookie_path.read_text(encoding="utf-8")

    # 2. 잘못된 텍스트 거부
    bad_resp = client.post(
        "/api/platforms/youtube/cookie-text",
        json={"text": "Cookie: VISITOR_INFO1_LIVE=123"},
    )
    assert bad_resp.status_code == 400

    # 3. 파일 업로드 엔드포인트
    valid_netscape = (
        "# Netscape HTTP Cookie File\n"
        ".youtube.com\tTRUE\t/\tTRUE\t0\tLOGIN_INFO\tuploaded_login\n"
        ".youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\tuploaded_sapi\n"
    )
    up_resp = client.post(
        "/api/platforms/youtube/cookie",
        files={"file": ("cookies.txt", io.BytesIO(valid_netscape.encode("utf-8")), "text/plain")},
    )
    assert up_resp.status_code == 200
    assert "uploaded_login" in fake_cookie_path.read_text(encoding="utf-8")

    # 4. 브라우저 로그인 엔드포인트
    with patch(
        "app.api.platforms.login_youtube_via_browser",
        new=AsyncMock(return_value=valid_netscape),
    ):
        login_resp = client.post("/api/platforms/youtube/browser-login")
        assert login_resp.status_code == 200
        assert fake_cookie_path.is_file()

    # 5. 삭제 엔드포인트
    del_resp = client.delete("/api/platforms/youtube/cookie")
    assert del_resp.status_code == 200
    assert not fake_cookie_path.exists()
