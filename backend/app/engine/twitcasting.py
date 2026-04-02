"""
Signal-Recorder: TwitCasting 엔진
TwitCasting API v2로 라이브 상태를 확인하고,
라이브 URL을 반환한다. 스트림 다운로드는 YtdlpLivePipeline에서 처리한다.
"""

from __future__ import annotations

import base64
from typing import Optional

import httpx

from app.core.config import get_settings
from app.core.logger import logger
from app.engine.base import LiveStatus

# ── TwitCasting API v2 ──────────────────────────────────────
TWITCASTING_API_BASE = "https://apiv2.twitcasting.tv"
TWITCASTING_LIVE_URL = "https://twitcasting.tv/{channel_id}"


class TwitcastingEngine:
    """TwitCasting 라이브 감지 + 스트림 추출 엔진.

    라이브 감지: TwitCasting API v2 `GET /users/{id}/current_live`
    스트림 추출: Streamlink twitcasting.tv 플러그인
    인증: Basic Auth (Client ID + Client Secret)
    """

    def _get_auth_header(self) -> dict[str, str]:
        """Basic Auth 헤더를 생성한다."""
        settings = get_settings()
        client_id = settings.twitcasting_client_id
        client_secret = settings.twitcasting_client_secret

        if not client_id or not client_secret:
            return {}

        credentials = f"{client_id}:{client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    async def check_live_status(self, channel_id: str) -> LiveStatus:
        """TwitCasting API v2로 채널의 라이브 상태를 확인한다.

        오프라인 시 404 응답이 반환되므로 예외 없이 처리한다.

        Args:
            channel_id: TwitCasting 사용자 ID (예: "someuser")

        Returns:
            LiveStatus 딕셔너리.
        """
        url = f"{TWITCASTING_API_BASE}/users/{channel_id}/current_live"
        headers = {
            "Accept": "application/json",
            **self._get_auth_header(),
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, headers=headers, timeout=10.0)
            except httpx.RequestError as e:
                logger.error(f"[TwitCasting:{channel_id}] API 요청 실패: {e}")
                return self._offline_status(channel_id)

        # 404 = 오프라인 (공식 동작)
        if resp.status_code == 404:
            return self._offline_status(channel_id)

        if resp.status_code != 200:
            logger.warning(f"[TwitCasting:{channel_id}] API 응답 {resp.status_code}")
            return self._offline_status(channel_id)

        try:
            data = resp.json()
        except Exception:
            return self._offline_status(channel_id)

        movie = data.get("movie") or {}
        broadcaster = data.get("broadcaster") or {}

        is_live = bool(movie.get("is_live", False))

        return LiveStatus(
            channel_id=channel_id,
            is_live=is_live,
            channel_name=broadcaster.get("screen_id") or broadcaster.get("name") or channel_id,
            title=movie.get("title", ""),
            category=movie.get("category") or "",
            viewer_count=movie.get("current_view_count", 0),
            thumbnail_url=movie.get("large_thumbnail", "") or "",
            profile_image_url=broadcaster.get("image") or "",
        )

    async def get_movie_list(
        self,
        channel_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> dict:
        """TwitCasting API v2로 채널의 과거 방송 목록을 조회한다.

        Args:
            channel_id: TwitCasting 사용자 ID
            offset: 페이지 오프셋 (0~1000)
            limit: 한 번에 가져올 개수 (1~50)

        Returns:
            {total_count, movies: [{id, title, duration, created_at,
             thumbnail_url, view_count, archive_url}]}
        """
        url = f"{TWITCASTING_API_BASE}/users/{channel_id}/movies"
        headers = {
            "Accept": "application/json",
            **self._get_auth_header(),
        }
        params = {"offset": offset, "limit": min(limit, 50)}

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, headers=headers, params=params, timeout=10.0)
            except httpx.RequestError as e:
                logger.error(f"[TwitCasting:{channel_id}] 아카이브 목록 요청 실패: {e}")
                raise RuntimeError(f"API 요청 실패: {e}") from e

        if resp.status_code == 401:
            raise PermissionError("TwitCasting 인증 실패: Client ID/Secret을 확인하세요.")
        if resp.status_code == 404:
            raise ValueError(f"채널을 찾을 수 없습니다: {channel_id}")
        if resp.status_code != 200:
            raise RuntimeError(f"TwitCasting API 오류: HTTP {resp.status_code}")

        data = resp.json()
        total_count = data.get("total_count", 0)
        raw_movies = data.get("movies", [])

        movies = []
        for item in raw_movies:
            movie = item.get("movie") or {}
            broadcaster = item.get("broadcaster") or {}
            movie_id = movie.get("id")
            if not movie_id:
                continue  # ID 없는 항목 스킵 (비정상 응답 방어)
            movie_id = str(movie_id)
            movies.append({
                "id": movie_id,
                "title": movie.get("title", ""),
                "duration": movie.get("duration", 0),
                "created_at": movie.get("created", 0),
                "thumbnail_url": movie.get("large_thumbnail", "") or "",
                "view_count": movie.get("total_view_count", 0),
                "channel_name": broadcaster.get("screen_id") or broadcaster.get("name") or channel_id,
                "archive_url": f"https://twitcasting.tv/{channel_id}/movie/{movie_id}",
            })

        return {"total_count": total_count, "movies": movies}

    def get_stream_url(self, channel_id: str) -> str:
        """TwitCasting 라이브 URL을 반환한다.

        실제 스트림 추출은 yt-dlp가 처리한다.

        Args:
            channel_id: TwitCasting 사용자 ID

        Returns:
            TwitCasting 라이브 URL 문자열.
        """
        return TWITCASTING_LIVE_URL.format(channel_id=channel_id)

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
        )
