"""
test_auth.py
쿠키 파싱, 헤더 생성, yt-dlp 쿠키 빌드 테스트
"""

from pathlib import Path
from unittest.mock import patch
import pytest
from app.engine.auth import AuthManager, ChzzkCookies
from app.core.config import Settings


class TestChzzkCookies:
    """ChzzkCookies 데이터 클래스 테스트"""

    def test_to_cookie_string(self):
        """Cookie 헤더 문자열 생성 테스트"""
        cookies = ChzzkCookies(nid_aut="test_aut", nid_ses="test_ses")
        cookie_string = cookies.to_cookie_string()

        assert cookie_string == "NID_AUT=test_aut; NID_SES=test_ses"

    def test_to_dict(self):
        """딕셔너리 변환 테스트"""
        cookies = ChzzkCookies(nid_aut="test_aut", nid_ses="test_ses")
        cookie_dict = cookies.to_dict()

        assert cookie_dict == {
            "NID_AUT": "test_aut",
            "NID_SES": "test_ses",
        }

    def test_immutability(self):
        """frozen=True로 인한 불변성 테스트"""
        cookies = ChzzkCookies(nid_aut="test_aut", nid_ses="test_ses")

        with pytest.raises(AttributeError):
            cookies.nid_aut = "modified"  # type: ignore[misc]

    def test_to_netscape_string_and_reusable_cookie_stream(self):
        """yt-dlp cookiefile용 Netscape 포맷 및 다중 컨텍스트 재사용 검증"""
        import yt_dlp

        cookies = ChzzkCookies(nid_aut="test_aut", nid_ses="test_ses")
        netscape = cookies.to_netscape_string()
        assert netscape.startswith("# Netscape HTTP Cookie File\n")
        assert ".naver.com\tTRUE\t/\tTRUE\t0\tNID_AUT\ttest_aut" in netscape
        assert ".naver.com\tTRUE\t/\tTRUE\t0\tNID_SES\ttest_ses" in netscape

        stream = cookies.to_cookie_stream()
        opts = {"quiet": True, "no_warnings": True, "cookiefile": stream}
        # 메타데이터 조회와 파일명 준비 등 여러 YoutubeDL 컨텍스트에서 재사용해도 쿠키가 유지되어야 한다.
        for _ in range(2):
            with yt_dlp.YoutubeDL(opts) as ydl:
                header = ydl.cookiejar.get_cookie_header("https://api.chzzk.naver.com/service/v3/videos/1")
                assert "NID_AUT=test_aut" in header
                assert "NID_SES=test_ses" in header


def test_classify_stderr_deprecated_feature_as_warning():
    """yt-dlp의 Deprecated Feature 메시지는 ERROR가 아닌 WARNING으로 분류되어야 한다."""
    import logging
    from app.core.logger import _classify_stderr_line

    level, body = _classify_stderr_line(
        "Deprecated Feature: Passing cookies as a header is a potential security risk"
    )
    assert level == logging.WARNING
    assert "Passing cookies as a header" in body


class TestAuthManager:
    """AuthManager 클래스 테스트"""

    def test_is_authenticated_true(self):
        """인증 쿠키가 설정된 경우"""
        auth = AuthManager(nid_aut="test_aut", nid_ses="test_ses")

        assert auth.is_authenticated is True

    def test_is_authenticated_false_no_cookies(self):
        """쿠키가 설정되지 않은 경우"""
        # get_settings()를 mock하여 쿠키 없는 Settings 반환
        mock_settings = Settings(nid_aut=None, nid_ses=None)

        with patch('app.engine.auth.get_settings', return_value=mock_settings):
            auth = AuthManager(nid_aut=None, nid_ses=None)
            assert auth.is_authenticated is False

    def test_is_authenticated_false_partial_cookies(self):
        """쿠키가 부분적으로만 설정된 경우"""
        mock_settings = Settings(nid_aut=None, nid_ses=None)

        with patch('app.engine.auth.get_settings', return_value=mock_settings):
            auth1 = AuthManager(nid_aut="test_aut", nid_ses=None)
            auth2 = AuthManager(nid_aut=None, nid_ses="test_ses")

            assert auth1.is_authenticated is False
            assert auth2.is_authenticated is False

    def test_get_cookies_authenticated(self):
        """인증된 경우 쿠키 객체 반환"""
        auth = AuthManager(nid_aut="test_aut", nid_ses="test_ses")
        cookies = auth.get_cookies()

        assert cookies is not None
        assert cookies.nid_aut == "test_aut"
        assert cookies.nid_ses == "test_ses"

    def test_get_cookies_unauthenticated(self):
        """비인증 상태에서는 None 반환"""
        mock_settings = Settings(nid_aut=None, nid_ses=None)

        with patch('app.engine.auth.get_settings', return_value=mock_settings):
            auth = AuthManager(nid_aut=None, nid_ses=None)
            cookies = auth.get_cookies()

            assert cookies is None

    def test_get_http_headers_with_cookies(self):
        """인증 쿠키가 있는 경우 HTTP 헤더"""
        auth = AuthManager(nid_aut="test_aut", nid_ses="test_ses")
        headers = auth.get_http_headers()

        assert "User-Agent" in headers
        assert "Cookie" in headers
        assert headers["Cookie"] == "NID_AUT=test_aut; NID_SES=test_ses"

    def test_get_http_headers_without_cookies(self):
        """인증 쿠키가 없는 경우 HTTP 헤더"""
        mock_settings = Settings(nid_aut=None, nid_ses=None)

        with patch('app.engine.auth.get_settings', return_value=mock_settings):
            auth = AuthManager(nid_aut=None, nid_ses=None)
            headers = auth.get_http_headers()

            assert "User-Agent" in headers
            assert "Cookie" not in headers

    def test_get_ytdlp_cookies_with_auth(self):
        """인증 쿠키가 있는 경우 yt-dlp 쿠키 문자열"""
        auth = AuthManager(nid_aut="test_aut", nid_ses="test_ses")
        ytdlp_cookies = auth.get_ytdlp_cookies()

        assert ytdlp_cookies == "NID_AUT=test_aut; NID_SES=test_ses"

    def test_get_ytdlp_cookies_without_auth(self):
        """인증 쿠키가 없는 경우 None 반환"""
        mock_settings = Settings(nid_aut=None, nid_ses=None)

        with patch('app.engine.auth.get_settings', return_value=mock_settings):
            auth = AuthManager(nid_aut=None, nid_ses=None)
            ytdlp_cookies = auth.get_ytdlp_cookies()

            assert ytdlp_cookies is None

    def test_update_cookies(self):
        """쿠키 업데이트 및 .env 파일 저장 테스트"""
        auth = AuthManager(nid_aut="old_aut", nid_ses="old_ses")

        with patch("app.core.utils.update_env_file") as mock_update:
            auth.update_cookies(nid_aut="new_aut", nid_ses="new_ses")

            # 런타임 값 업데이트 확인
            assert auth._nid_aut == "new_aut"
            assert auth._nid_ses == "new_ses"
            assert auth.is_authenticated is True

            # .env 저장 함수 호출 확인
            mock_update.assert_called_once_with({"NID_AUT": "new_aut", "NID_SES": "new_ses"})

    def test_update_cookies_no_env_file(self):
        """
        런타임 쿠키 업데이트는 파일 저장 성공 여부와 관계없이 동작해야 함
        """
        auth = AuthManager(nid_aut="old_aut", nid_ses="old_ses")

        with patch("app.core.utils.update_env_file") as mock_update:
            auth.update_cookies(nid_aut="new_aut", nid_ses="new_ses")

            # 런타임 값은 업데이트됨
            assert auth._nid_aut == "new_aut"
            assert auth._nid_ses == "new_ses"
            assert auth.is_authenticated is True
            mock_update.assert_called_once()
