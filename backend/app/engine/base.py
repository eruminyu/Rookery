"""
Signal-Recorder: 멀티 플랫폼 엔진 공통 인터페이스
Platform Enum, LiveStatus TypedDict, PlatformEngine Protocol을 정의한다.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from typing_extensions import TypedDict, Protocol, runtime_checkable


class Platform(str, Enum):
    """지원 플랫폼 열거형."""

    CHZZK = "chzzk"
    TWITCASTING = "twitcasting"
    X_SPACES = "x_spaces"
    YOUTUBE = "youtube"


class LiveStatus(TypedDict, total=False):
    """플랫폼 공통 라이브 상태 정보."""

    channel_id: str
    is_live: bool
    channel_name: str
    title: str
    category: str
    viewer_count: int
    thumbnail_url: str
    profile_image_url: str
    # X Spaces 전용: 녹화에 필요한 space_id
    space_id: Optional[str]
    # X Spaces 전용: 라이브 중 캡처한 dynamic m3u8 URL
    m3u8_url: Optional[str]
    # X Spaces 전용: master_playlist.m3u8 (쿼리파라미터 없음, 종료 후 ~30일 유효)
    master_url: Optional[str]


@runtime_checkable
class PlatformEngine(Protocol):
    """플랫폼 엔진 프로토콜.

    StreamLinkEngine, TwitcastingEngine, XSpacesEngine이 이를 구현한다.
    @runtime_checkable 덕분에 isinstance() 체크 가능.
    """

    async def check_live_status(self, channel_id: str) -> LiveStatus:
        """채널의 라이브 상태를 확인한다."""
        ...

    def get_stream(self, channel_id: str, quality: str = "best") -> object:
        """스트림 객체를 반환한다 (X Spaces는 NotImplementedError)."""
        ...
