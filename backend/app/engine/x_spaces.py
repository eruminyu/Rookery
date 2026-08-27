"""
Rookery: X Spaces 엔진
비공식 GraphQL API + 쿠키 인증으로 Space 라이브 상태를 확인하고,
라이브 중일 때 dynamic_playlist.m3u8 URL을 캡처하여 반환한다.

다운로드는 종료 후 캡처된 m3u8 URL을 VodEngine(yt-dlp/ffmpeg)에 넘겨 처리한다.

인증 방식:
- Netscape 형식 쿠키 파일에서 auth_token, ct0 추출
- X 내부 GraphQL API 호출 (비공식)

참고:
- AudioSpaceById QUERY_ID는 X 배포마다 변경될 수 있음
- channel_id: @핸들 제외한 username (예: KalserianT)
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import get_settings
from app.core.logger import logger
from app.engine.base import LiveStatus

# ── 상수 ────────────────────────────────────────────────────────────
X_SPACES_URL = "https://x.com/i/spaces/{space_id}"

# X 웹 클라이언트에 하드코딩된 공개 Bearer 토큰
_BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# GraphQL QUERY_ID — X 배포마다 변경될 수 있음
# 최신값 확인: yt-dlp/yt-dlp twitter.py, trevorhobenshield/twitter-api-client constants.py
_AUDIO_SPACE_BY_ID_QUERY_ID = "HPEisOmj1epUNLCWTYhUWw"
_USER_BY_SCREEN_NAME_QUERY_ID = "oUZZZ8Oddwxs8Cd3iW3UEA"
# AudioSpaceSearch는 X API deprecated — UserTweets 방식으로 탐색
_USER_TWEETS_QUERY_IDS = [
    "rIIwMe1ObkGh_ByBtTCtRQ",  # 최신 (twspace-crawler 2023.07 기준)
    "V7H0Ap3_Hh2FyS75OCDO3Q",  # 구버전 fallback
    "CdG2Vuc1v6F5JyEngGpxVw",  # 구버전 fallback 2
]

# Space 상태값 (AudioSpaceById 응답의 metadata.state)
SPACE_STATE_RUNNING = "Running"
SPACE_STATE_ENDED = "Ended"
SPACE_STATE_NOT_STARTED = "NotStarted"


class XSpacesEngine:
    """X Spaces 라이브 감지 + m3u8 URL 캡처 엔진.

    라이브 감지: 비공식 GraphQL AudioSpaceById API (쿠키 인증)
    감지 방식: username → user_id → 활성 Space 확인
    m3u8 캡처: live_video_stream/status/{media_key} 에서 URL 추출
    다운로드: 캡처한 URL을 VodEngine(yt-dlp)에 전달 (별도 처리)
    """

    async def check_live_status(self, channel_id: str) -> LiveStatus:
        """비공식 GraphQL API로 사용자의 활성 Space를 확인하고 m3u8 URL을 캡처한다.

        Args:
            channel_id: X username (예: "KalserianT"). @핸들 제외.

        Returns:
            LiveStatus 딕셔너리.
            is_live=True 시 space_id와 m3u8_url 포함.
        """
        # "@username" 형태로 입력해도 정상 처리
        channel_id = channel_id.lstrip("@")

        settings = get_settings()
        cookie_file = settings.x_cookie_file

        if not cookie_file or not Path(cookie_file).is_file():
            logger.warning(
                f"[XSpaces:{channel_id}] 쿠키 파일이 설정되지 않았거나 없습니다: {cookie_file}"
            )
            return self._offline_status(channel_id)

        cookies = _parse_netscape_cookies(cookie_file)
        if not cookies.get("auth_token") or not cookies.get("ct0"):
            logger.warning(
                f"[XSpaces:{channel_id}] 쿠키 파일에서 auth_token/ct0를 찾을 수 없습니다."
            )
            return self._offline_status(channel_id)

        headers = _build_headers(cookies["ct0"])

        try:
            async with httpx.AsyncClient(
                cookies=cookies,
                headers=headers,
                timeout=15.0,
                follow_redirects=True,
            ) as client:
                # 1단계: UserByScreenName으로 user_id 조회
                user_id = await _get_user_id(client, channel_id)
                if user_id is None:
                    logger.warning(f"[XSpaces:{channel_id}] user_id 조회 실패 (쿠키 만료 또는 존재하지 않는 계정).")
                    return self._offline_status(channel_id)

                # 2단계: UserTweets 타임라인에서 활성 Space 탐색
                space_info = await _get_active_space(client, user_id, channel_id)
                if space_info is None:
                    logger.info(f"[XSpaces:{channel_id}] 활성 Space 없음 (오프라인).")
                    return self._offline_status(channel_id)
                space_id = space_info["space_id"]

                # 3단계: AudioSpaceById로 media_key + title 조회
                space_meta = await get_space_by_id(client, space_id)
                if space_meta is None:
                    logger.warning(f"[XSpaces:{channel_id}] Space 메타데이터 조회 실패: {space_id}")
                    return self._offline_status(channel_id)

                # state가 Running이 아니면 오프라인 처리 (종료된 Space가 타임라인에 남아있는 경우 대비)
                if space_meta["state"] != SPACE_STATE_RUNNING:
                    logger.info(
                        f"[XSpaces:{channel_id}] Space 종료됨 "
                        f"(state={space_meta['state']}, space_id={space_id})"
                    )
                    return self._offline_status(channel_id)

                title = space_meta["title"]
                media_key = space_meta["media_key"]

                # 4단계: m3u8 URL 캡처 + master URL 유도
                m3u8_url: Optional[str] = None
                master_url: Optional[str] = None
                if media_key:
                    m3u8_url = await _get_m3u8_url(client, media_key, channel_id)
                    if m3u8_url:
                        master_url = _derive_master_url(m3u8_url)

                logger.info(
                    f"[XSpaces:{channel_id}] 라이브 Space 감지: {space_id} — {title}"
                    + (" (master URL 캡처 완료)" if master_url else " (m3u8 캡처 실패)")
                )

                return LiveStatus(
                    channel_id=channel_id,
                    is_live=True,
                    channel_name=channel_id,
                    title=title,
                    category="X Spaces",
                    viewer_count=0,
                    thumbnail_url="",
                    profile_image_url="",
                    space_id=space_id,
                    m3u8_url=m3u8_url,
                    master_url=master_url,
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning(
                    f"[XSpaces:{channel_id}] 쿠키 인증 만료 (401). "
                    "쿠키 파일을 다시 추출해주세요."
                )
            else:
                logger.error(
                    f"[XSpaces:{channel_id}] HTTP 오류 {e.response.status_code}: {e}"
                )
            return self._offline_status(channel_id)
        except httpx.RequestError as e:
            logger.error(f"[XSpaces:{channel_id}] 네트워크 오류: {e}")
            return self._offline_status(channel_id)
        except Exception as e:
            logger.error(f"[XSpaces:{channel_id}] 예상치 못한 오류: {e}", exc_info=e)
            return self._offline_status(channel_id)

    async def start_ytdlp_recording(
        self,
        space_id: str,
        output_dir: str,
        channel_name: str,
        title: Optional[str] = None,
        cookie_file: Optional[str] = None,
    ) -> object:
        """yt-dlp subprocess로 X Spaces를 다운로드한다.

        m3u8 URL 캡처에 실패했을 때의 fallback — space_id URL로 시도.
        """
        ytdlp_path = get_settings().resolve_ytdlp_path()
        space_url = X_SPACES_URL.format(space_id=space_id)

        safe_channel = _sanitize_filename(channel_name)
        safe_title = _sanitize_filename(title or "X Spaces")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"[{safe_channel}] {safe_title}_{timestamp}.m4a"

        output_path = Path(output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            ytdlp_path,
            space_url,
            "--output", str(output_path),
            "--format", "bestaudio",
            "--no-progress",
            "--quiet",
        ]

        if cookie_file and Path(cookie_file).is_file():
            cmd.extend(["--cookies", cookie_file])
        elif cookie_file:
            logger.warning(f"[XSpaces] 쿠키 파일을 찾을 수 없습니다: {cookie_file}")

        logger.info(f"[XSpaces] yt-dlp 다운로드 시작: {output_path}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return process, str(output_path)

    async def download_by_space_url(
        self,
        space_url: str,
        output_dir: str,
        cookie_file: Optional[str] = None,
    ) -> dict:
        """Space URL로 직접 다운로드한다.

        UserTweets API를 사용하지 않고 space_id → AudioSpaceById → m3u8 → yt-dlp 흐름으로 처리.
        라이브 중인 Space와 종료된 Space(약 30일 이내) 모두 지원.

        Args:
            space_url: X/Twitter Space URL.
                       예: https://x.com/i/spaces/1BdGYyg...
                       또는 https://twitter.com/i/spaces/1BdGYyg...
            output_dir: 다운로드 저장 디렉토리.
            cookie_file: Netscape 형식 쿠키 파일 경로. None이면 설정에서 가져옴.

        Returns:
            성공: {"started": True, "space_id": ..., "title": ..., "state": ..., "output": ...}
            실패: {"error": "오류 메시지"}
        """
        # 1. space_id 추출
        match = re.search(r"/spaces/([A-Za-z0-9]+)", space_url)
        if not match:
            return {"error": f"Space URL에서 space_id를 추출할 수 없습니다: {space_url}"}
        space_id = match.group(1)

        # 2. 쿠키 로드
        cookie_file_path = cookie_file or get_settings().x_cookie_file
        if not cookie_file_path or not Path(cookie_file_path).is_file():
            return {"error": "X 쿠키 파일이 설정되지 않았습니다. 설정 페이지에서 쿠키 파일을 업로드해주세요."}

        cookies = _parse_netscape_cookies(cookie_file_path)
        if not cookies.get("auth_token") or not cookies.get("ct0"):
            return {"error": "쿠키 파일에서 auth_token/ct0를 찾을 수 없습니다. 쿠키 파일을 다시 추출해주세요."}

        headers = _build_headers(cookies["ct0"])

        try:
            async with httpx.AsyncClient(
                cookies=cookies,
                headers=headers,
                timeout=15.0,
                follow_redirects=True,
            ) as client:
                # 3. AudioSpaceById로 Space 메타데이터 조회
                space_info = await get_space_by_id(client, space_id)
                if space_info is None:
                    return {"error": f"Space 정보를 가져올 수 없습니다. space_id={space_id} — 쿠키 만료 또는 비공개 Space일 수 있습니다."}

                state = space_info["state"]
                media_key = space_info["media_key"]
                title = space_info["title"]

                if state == SPACE_STATE_NOT_STARTED:
                    return {"error": f"Space가 아직 시작되지 않았습니다: {title}"}

                if not media_key:
                    return {"error": f"media_key를 가져올 수 없습니다 (state={state}). 종료 후 시간이 너무 지났을 수 있습니다."}

                # 4. m3u8 URL 조회
                m3u8_url = await _get_m3u8_url(client, media_key, space_id)
                if not m3u8_url:
                    return {"error": "m3u8 URL을 가져올 수 없습니다. 종료된 지 오래된 Space이거나 비공개 Space일 수 있습니다."}

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return {"error": "X 쿠키가 만료되었습니다. 브라우저에서 쿠키를 다시 추출해주세요."}
            return {"error": f"X API 오류 (HTTP {e.response.status_code})"}
        except Exception as e:
            logger.error(f"[XSpaces] Space 정보 조회 실패 (space_id={space_id}): {e}", exc_info=e)
            return {"error": str(e)}

        # 5. yt-dlp subprocess로 다운로드 시작 (start_ytdlp_recording과 동일 패턴)
        safe_title = _sanitize_filename(title)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"[XSpaces] {safe_title}_{timestamp}.m4a"

        output_path = Path(output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        ytdlp_path = get_settings().resolve_ytdlp_path()
        cmd = [
            ytdlp_path,
            m3u8_url,
            "--output", str(output_path),
            "--format", "bestaudio",
            "--no-progress",
            "--quiet",
        ]
        if cookie_file_path:
            cmd.extend(["--cookies", cookie_file_path])

        logger.info(f"[XSpaces] 다운로드 시작: {title} ({state}) → {output_path}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        async def _wait_and_log() -> None:
            _, stderr = await process.communicate()
            if process.returncode == 0:
                logger.info(f"[XSpaces] 다운로드 완료: {output_path}")
            else:
                err_msg = stderr.decode(errors="replace").strip()[:300]
                logger.error(f"[XSpaces] 다운로드 실패 (exit={process.returncode}): {err_msg}")

        asyncio.create_task(_wait_and_log())

        return {
            "started": True,
            "space_id": space_id,
            "title": title,
            "state": state,
            "output": str(output_path),
        }

    @staticmethod
    def _offline_status(channel_id: str) -> LiveStatus:
        """오프라인 상태 딕셔너리를 반환한다."""
        return LiveStatus(
            channel_id=channel_id,
            is_live=False,
            channel_name=channel_id,
            title="",
            category="",
            viewer_count=0,
            thumbnail_url="",
            profile_image_url="",
            space_id=None,
            m3u8_url=None,
        )


# ── 내부 헬퍼 함수 ───────────────────────────────────────────────────

def _parse_netscape_cookies(cookie_file: str) -> dict[str, str]:
    """Netscape 형식 쿠키 파일에서 X 인증에 필요한 쿠키를 추출한다.

    Returns:
        {"auth_token": "...", "ct0": "...", ...} 형태의 딕셔너리.
        필요한 키가 없으면 빈 딕셔너리.
    """
    result: dict[str, str] = {}
    target_keys = {"auth_token", "ct0"}

    try:
        with open(cookie_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    name = parts[5]
                    value = parts[6]
                    if name in target_keys:
                        result[name] = value
    except Exception as e:
        logger.error(f"쿠키 파일 파싱 실패: {cookie_file} — {e}")

    return result


def _build_headers(ct0: str) -> dict[str, str]:
    """X 내부 API 호출에 필요한 헤더를 구성한다."""
    return {
        "Authorization": f"Bearer {_BEARER_TOKEN}",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Client",
        "x-twitter-client-language": "ko",
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }


async def _get_user_id(client: httpx.AsyncClient, username: str) -> Optional[str]:
    """GraphQL UserByScreenName으로 user_id를 조회한다."""
    variables = json.dumps({
        "screen_name": username,
        "withSafetyModeUserFields": True,
    })
    features = json.dumps({
        "hidden_profile_likes_enabled": True,
        "hidden_profile_subscriptions_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "subscriptions_verification_info_is_identity_verified_enabled": True,
        "subscriptions_verification_info_verified_since_enabled": True,
        "highlights_tweets_tab_ui_enabled": True,
        "responsive_web_twitter_article_notes_tab_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
    })

    try:
        resp = await client.get(
            f"https://twitter.com/i/api/graphql/{_USER_BY_SCREEN_NAME_QUERY_ID}/UserByScreenName",
            params={"variables": variables, "features": features},
        )
        resp.raise_for_status()
        data = resp.json()
        user = data.get("data", {}).get("user", {}).get("result", {})
        return user.get("rest_id")
    except Exception as e:
        logger.warning(f"UserByScreenName 조회 실패 ({username}): {e}")
        return None


async def _get_active_space(
    client: httpx.AsyncClient,
    user_id: str,
    username: str,
) -> Optional[dict]:
    """AudioSpaceSearch 또는 UserTweets 타임라인에서 활성 Space를 탐색한다.

    Returns:
        {"space_id": ..., "title": ..., "media_key": ...} 또는 None.
    """
    # UserTweets 타임라인에서 Space 관련 트윗 탐색
    variables = json.dumps({
        "userId": user_id,
        "count": 20,
        "includePromotedContent": False,
        "withQuickPromoteEligibilityTweetFields": False,
        "withVoice": True,
        "withV2Timeline": True,
    })
    features = json.dumps({
        "rweb_lists_timeline_redesign_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": False,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_media_download_video_enabled": False,
        "responsive_web_enhance_cards_enabled": False,
    })

    # 여러 QUERY_ID 후보를 순서대로 시도 (X 배포마다 변경되므로)
    for qid in _USER_TWEETS_QUERY_IDS:
        try:
            resp = await client.get(
                f"https://twitter.com/i/api/graphql/{qid}/UserTweets",
                params={"variables": variables, "features": features},
            )
            if resp.status_code == 400:
                continue
            resp.raise_for_status()
            data = resp.json()
            space_info = _extract_space_from_timeline(data)
            if space_info:
                return space_info
            # 응답은 왔지만 Space 없음 → 오프라인 (qid 성공 확인용 디버그 로그)
            logger.debug(f"[XSpaces:{username}] UserTweets 성공 (qid={qid}) — Space 없음 또는 파싱 실패")
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning(f"[XSpaces:{username}] UserTweets 레이트 리밋 (429). 다음 폴링까지 대기.")
            else:
                logger.warning(f"UserTweets HTTP 오류 (qid={qid}): {e.response.status_code} — {e.response.text[:200]}")
            continue
        except Exception as e:
            logger.warning(f"UserTweets 조회 실패 (qid={qid}): {e}")
            continue

    # 타임라인 실패 시 AudioSpaceById로 직접 시도 (space_id를 모르면 불가, fallback 없음)
    logger.warning(f"[XSpaces:{username}] 모든 타임라인 쿼리 실패.")
    return None


def _extract_space_id_from_url(url: str) -> Optional[str]:
    """URL에서 space_id를 추출한다. /i/spaces/{id} 패턴."""
    if "/i/spaces/" not in url:
        return None
    try:
        return url.rstrip("/").split("/i/spaces/")[1].split("?")[0].split("/")[0]
    except IndexError:
        return None


def _extract_space_from_timeline(data: dict) -> Optional[dict]:
    """UserTweets GraphQL 응답에서 활성 Space 정보를 추출한다.

    탐색 순서:
    1. tweet.legacy.entities.urls[].expanded_url (가장 안정적)
    2. card.legacy.binding_values list 형식 (구버전 호환)
    3. card.legacy.binding_values dict 형식 (신버전)
    """
    try:
        instructions = (
            data.get("data", {})
            .get("user", {})
            .get("result", {})
            .get("timeline_v2", {})
            .get("timeline", {})
            .get("instructions", [])
        )
        for instruction in instructions:
            for entry in instruction.get("entries", []):
                content = entry.get("content", {})
                tweet_result = (
                    content.get("itemContent", {})
                    .get("tweet_results", {})
                    .get("result", {})
                )
                if not tweet_result:
                    continue

                tweet_legacy = tweet_result.get("legacy", {})

                # 방법 1: entities.urls (가장 안정적)
                for url_entity in tweet_legacy.get("entities", {}).get("urls", []):
                    for key in ("expanded_url", "url", "display_url"):
                        space_id = _extract_space_id_from_url(url_entity.get(key, ""))
                        if space_id:
                            return {"space_id": space_id, "title": "X Spaces", "media_key": None}

                # 방법 2: card.legacy.binding_values (list 형식)
                card = tweet_result.get("card", {})
                card_legacy = card.get("legacy", {})
                binding_values = card_legacy.get("binding_values", [])

                if isinstance(binding_values, list):
                    title = ""
                    space_id = None
                    for bv in binding_values:
                        key = bv.get("key", "")
                        val = bv.get("value", {})
                        if key == "card_url":
                            url = val.get("scribe_value", {}).get("value", "") or val.get("string_value", "")
                            space_id = _extract_space_id_from_url(url)
                        elif key == "title":
                            title = val.get("string_value", "")
                    if space_id:
                        return {"space_id": space_id, "title": title or "X Spaces", "media_key": None}

                elif isinstance(binding_values, dict):
                    # 방법 3: binding_values dict 형식 (신버전)
                    card_url_obj = binding_values.get("card_url", {})
                    url = card_url_obj.get("string_value", "")
                    space_id = _extract_space_id_from_url(url)
                    if space_id:
                        title = binding_values.get("title", {}).get("string_value", "X Spaces")
                        return {"space_id": space_id, "title": title, "media_key": None}

    except Exception:
        pass
    return None


def _derive_master_url(dynamic_url: str) -> str:
    """dynamic_playlist.m3u8 URL에서 master_playlist.m3u8 URL을 유도한다.

    master URL은 쿼리파라미터 없이 안정적 — 종료 후 약 30일간 유효.

    Args:
        dynamic_url: live_video_stream에서 반환된 dynamic_playlist.m3u8?token=... URL.

    Returns:
        master_playlist.m3u8 URL (쿼리파라미터 제거).
    """
    return dynamic_url.split("?")[0].replace("dynamic_playlist", "master_playlist")


async def get_space_by_id(
    client: httpx.AsyncClient,
    space_id: str,
) -> Optional[dict]:
    """AudioSpaceById로 특정 Space의 상태와 media_key를 조회한다."""
    variables = json.dumps({
        "id": space_id,
        "isMetatagsQuery": False,
        "withSuperFollowsUserFields": False,
        "withUserResults": True,
        "withBirdwatchPivots": False,
        "withReactionsMetadata": False,
        "withReactionsPerspective": False,
        "withSuperFollowsTweetFields": False,
        "withReplays": True,
        "withScheduledSpaces": False,
        "withDownvotePerspective": False,
    })

    try:
        resp = await client.get(
            f"https://twitter.com/i/api/graphql/{_AUDIO_SPACE_BY_ID_QUERY_ID}/AudioSpaceById",
            params={"variables": variables},
        )
        resp.raise_for_status()
        data = resp.json()
        metadata = data.get("data", {}).get("audioSpace", {}).get("metadata", {})
        state = metadata.get("state", "")  # "Running" or "Ended" or "NotStarted"
        media_key = metadata.get("media_key")
        title = metadata.get("title", "X Spaces")
        return {"state": state, "media_key": media_key, "title": title}
    except Exception as e:
        logger.debug(f"AudioSpaceById 조회 실패 (space_id={space_id}): {e}")
        return None


async def _get_m3u8_url(
    client: httpx.AsyncClient,
    media_key: str,
    username: str,
) -> Optional[str]:
    """live_video_stream/status/{media_key}에서 m3u8 URL을 추출한다."""
    try:
        resp = await client.get(
            f"https://twitter.com/i/api/1.1/live_video_stream/status/{media_key}",
            params={"client": "web", "use_syndication_guest_id": "false", "cookie_set_token": "xx"},
        )
        resp.raise_for_status()
        data = resp.json()
        location = data.get("source", {}).get("location", "")
        if location and "m3u8" in location:
            return location
        logger.debug(f"[XSpaces:{username}] m3u8 URL 없음. 응답: {str(data)[:200]}")
        return None
    except Exception as e:
        logger.debug(f"[XSpaces:{username}] live_video_stream 조회 실패: {e}")
        return None


def _sanitize_filename(name: str) -> str:
    """파일명에 사용 불가한 문자를 제거한다."""
    invalid = r'\/:*?"<>|'
    for ch in invalid:
        name = name.replace(ch, "_")
    return name.strip()[:50]


async def verify_cookie(cookie_file: str) -> dict:
    """쿠키 파일의 auth_token/ct0로 X 인증 유효성을 확인한다.

    X API verify_credentials 엔드포인트를 호출하여 쿠키 만료 여부를 판단한다.

    Args:
        cookie_file: Netscape 형식 쿠키 파일 경로.

    Returns:
        {"valid": bool, "checked_at": ISO8601 str, "reason": str | None}
    """
    checked_at = datetime.now().isoformat()

    if not cookie_file or not Path(cookie_file).is_file():
        return {
            "valid": False,
            "checked_at": checked_at,
            "reason": f"쿠키 파일을 찾을 수 없습니다: {cookie_file}",
        }

    cookies = _parse_netscape_cookies(cookie_file)
    if not cookies.get("auth_token") or not cookies.get("ct0"):
        return {
            "valid": False,
            "checked_at": checked_at,
            "reason": "쿠키 파일에서 auth_token/ct0를 찾을 수 없습니다.",
        }

    headers = _build_headers(cookies["ct0"])

    try:
        async with httpx.AsyncClient(
            cookies=cookies,
            headers=headers,
            timeout=10.0,
            follow_redirects=True,
        ) as client:
            # account/verify_credentials.json은 deprecated → UserByScreenName으로 대체
            variables = json.dumps({
                "screen_name": "x",
                "withSafetyModeUserFields": True,
            })
            features = json.dumps({
                "hidden_profile_likes_enabled": True,
                "hidden_profile_subscriptions_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False,
                "subscriptions_verification_info_is_identity_verified_enabled": True,
                "subscriptions_verification_info_verified_since_enabled": True,
                "highlights_tweets_tab_ui_enabled": True,
                "responsive_web_twitter_article_notes_tab_enabled": False,
                "creator_subscriptions_tweet_preview_api_enabled": True,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "responsive_web_graphql_timeline_navigation_enabled": True,
            })
            resp = await client.get(
                f"https://twitter.com/i/api/graphql/{_USER_BY_SCREEN_NAME_QUERY_ID}/UserByScreenName",
                params={"variables": variables, "features": features},
            )
            if resp.status_code == 200:
                return {"valid": True, "checked_at": checked_at, "reason": None}
            elif resp.status_code == 401:
                return {
                    "valid": False,
                    "checked_at": checked_at,
                    "reason": "쿠키가 만료되었습니다. 브라우저에서 쿠키를 다시 추출해주세요.",
                }
            else:
                return {
                    "valid": False,
                    "checked_at": checked_at,
                    "reason": f"X API 응답 오류 (HTTP {resp.status_code})",
                }
    except httpx.RequestError as e:
        return {
            "valid": False,
            "checked_at": checked_at,
            "reason": f"네트워크 오류: {e}",
        }
    except Exception as e:
        return {
            "valid": False,
            "checked_at": checked_at,
            "reason": f"예상치 못한 오류: {e}",
        }
