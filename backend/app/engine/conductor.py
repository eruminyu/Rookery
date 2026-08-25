"""
Signal-Recorder: Conductor (비동기 오케스트레이터)
다중 채널 감시 루프를 관리하고, 방송 시작 시 자동 녹화를 트리거한다.
멀티 플랫폼(Chzzk, TwitCasting, X Spaces)을 단일 Conductor로 통합 관리한다.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from app.core.config import get_settings, resolve_data_dir
from app.core.logger import logger
from app.engine.auth import AuthManager
from app.engine.base import Platform
from app.engine.chat import ChatArchiver
from app.engine.downloader import ChzzkLiveEngine
from app.engine.pipeline import YtdlpLivePipeline, RecordingState
from app.services.notifications import NotificationKind

if TYPE_CHECKING:
    from app.services.notifications import NotificationService
    from app.engine.twitcasting import TwitcastingEngine
    from app.engine.x_spaces import XSpacesEngine
    from app.engine.youtube import YoutubeLiveEngine


@dataclass
class ChannelTask:
    """감시 대상 채널 정보."""

    channel_id: str
    platform: Platform = Platform.CHZZK
    auto_record: bool = True
    pipeline: Optional[YtdlpLivePipeline] = field(default=None, repr=False)
    chat_archiver: Optional[ChatArchiver] = field(default=None, repr=False)
    monitor_task: Optional[asyncio.Task] = field(default=None, repr=False)
    is_live: bool = False
    channel_name: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    viewer_count: int = 0
    thumbnail_url: Optional[str] = None
    profile_image_url: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    last_error: Optional[str] = None
    # X Spaces 전용
    spaces_process: Optional[asyncio.subprocess.Process] = field(default=None, repr=False)
    spaces_output_path: Optional[str] = None
    _current_space_id: Optional[str] = None
    # X Spaces 전용: 라이브 중 캡처한 dynamic m3u8 URL
    captured_m3u8_url: Optional[str] = None
    captured_m3u8_at: Optional[str] = None
    # X Spaces 전용: master_playlist.m3u8 (안정적, 종료 후 ~30일 유효)
    master_url: Optional[str] = None
    master_url_captured_at: Optional[str] = None
    # X Spaces 전용: master URL이 저장된 .txt 파일 경로 (녹화 실패 시 백업용)
    master_url_file: Optional[str] = None


class Conductor:
    """비동기 오케스트레이터.

    Python asyncio를 활용하여 단일 스레드로 수십 개의 채널을 동시 감시한다.
    Chzzk, TwitCasting, X Spaces를 통합 관리한다.

    채널 키 형식: "platform:channel_id" (예: "chzzk:abc123", "twitcasting:someuser")
    기존 Chzzk 전용 키("abc123")는 자동으로 "chzzk:abc123"으로 마이그레이션된다.

    주요 기능:
        - 채널 등록/제거 (플랫폼 포함)
        - 주기적 라이브 상태 확인
        - 방송 시작 감지 시 자동 녹화 트리거
        - 방송 종료 감지 시 녹화 중지
    """

    # 쿠키 검증 주기 (초) — 하루 1회
    _COOKIE_CHECK_INTERVAL = 86400
    # X Spaces 폴링 주기 (초) — 레이트 리밋 방어를 위해 5분 간격
    _X_SPACES_POLL_INTERVAL = 300

    def __init__(
        self,
        auth: Optional[AuthManager] = None,
        notifier: Optional[NotificationService] = None,
    ) -> None:
        settings = get_settings()
        self._auth = auth or AuthManager()
        self._chzzk_engine = ChzzkLiveEngine(auth=self._auth)
        self._twitcasting_engine: Optional[TwitcastingEngine] = None
        self._x_spaces_engine: Optional[XSpacesEngine] = None
        self._youtube_engine: Optional[YoutubeLiveEngine] = None
        self._channels: dict[str, ChannelTask] = {}
        self._running = False
        _data_dir = resolve_data_dir()
        self._persistence_path = _data_dir / "channels.json"
        self._notifier = notifier
        self._event_queues: list[asyncio.Queue] = []
        # 라이브 감지 이력: composite_key → 날짜 문자열 set (하루 1회 카운트)
        self._live_detections: dict[str, set[str]] = {}
        self._live_history_path = _data_dir / "live_history.json"
        # 즉시 스캔 이벤트: composite_key → asyncio.Event
        self._scan_events: dict[str, asyncio.Event] = {}
        # X 쿠키 유효성 상태
        self._cookie_status: dict = {"valid": True, "checked_at": None, "reason": None}
        self._last_cookie_check: Optional[datetime] = None
        self._cookie_check_task: Optional[asyncio.Task] = None
        self._stats_broadcast_task: Optional[asyncio.Task] = None
        self._load_persistence()

    def _notify(
        self,
        kind: NotificationKind,
        title: str,
        description: str = "",
        color: str = "green",
        fields: Optional[dict[str, str]] = None,
    ) -> None:
        """알림을 큐에 넣는다. 논블로킹이며 실패해도 감시 루프를 막지 않는다.

        기존에는 감시 루프 안에서 Discord 응답을 await 했기 때문에
        레이트 리밋이 걸리면 라이브 감지와 녹화 시작까지 함께 지연됐다.
        """
        if self._notifier is None:
            return
        self._notifier.notify(
            kind=kind,
            title=title,
            description=description,
            color=color,
            fields=fields,
        )

    def _get_engine(self, platform: Platform):
        """플랫폼에 맞는 엔진 인스턴스를 반환한다."""
        if platform == Platform.CHZZK:
            return self._chzzk_engine
        elif platform == Platform.TWITCASTING:
            if self._twitcasting_engine is None:
                from app.engine.twitcasting import TwitcastingEngine
                self._twitcasting_engine = TwitcastingEngine()
            return self._twitcasting_engine
        elif platform == Platform.X_SPACES:
            if self._x_spaces_engine is None:
                from app.engine.x_spaces import XSpacesEngine
                self._x_spaces_engine = XSpacesEngine()
            return self._x_spaces_engine
        elif platform == Platform.YOUTUBE:
            if self._youtube_engine is None:
                from app.engine.youtube import YoutubeLiveEngine
                self._youtube_engine = YoutubeLiveEngine()
            return self._youtube_engine
        else:
            raise ValueError(f"지원하지 않는 플랫폼: {platform}")

    @staticmethod
    def make_composite_key(platform: Platform, channel_id: str) -> str:
        """복합 키를 생성한다."""
        return f"{platform.value}:{channel_id}"

    @staticmethod
    def parse_composite_key(key: str) -> tuple[Platform, str]:
        """복합 키를 (Platform, channel_id)로 파싱한다.

        ':' 없는 레거시 키는 Chzzk 채널로 처리한다.
        """
        if ":" not in key:
            return Platform.CHZZK, key
        platform_str, channel_id = key.split(":", 1)
        try:
            return Platform(platform_str), channel_id
        except ValueError:
            logger.warning(f"알 수 없는 플랫폼 값 '{platform_str}', Chzzk으로 처리합니다.")
            return Platform.CHZZK, channel_id

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def channel_count(self) -> int:
        return len(self._channels)

    def add_channel(
        self,
        channel_id: str,
        auto_record: bool = True,
        platform: Platform = Platform.CHZZK,
    ) -> None:
        """감시할 채널을 등록한다."""
        composite_key = self.make_composite_key(platform, channel_id)

        if composite_key in self._channels:
            logger.warning(f"채널 '{composite_key}'은(는) 이미 등록되어 있습니다.")
            return

        task = ChannelTask(
            channel_id=channel_id,
            platform=platform,
            auto_record=auto_record,
        )
        self._channels[composite_key] = task
        self._scan_events[composite_key] = asyncio.Event()
        logger.info(f"채널 등록: {composite_key} (auto_record={auto_record})")

        self._save_persistence()

        # 이미 실행 중이면 즉시 감시 시작
        if self._running:
            task.monitor_task = asyncio.create_task(
                self._monitor_channel(composite_key)
            )

    def set_auto_record(self, composite_key: str, value: bool) -> None:
        """채널의 자동 녹화 설정을 직접 지정한다."""
        task = self._channels.get(composite_key)
        if task is None:
            raise ValueError(f"채널 '{composite_key}'을(를) 찾을 수 없습니다.")
        task.auto_record = value
        logger.info(f"[{composite_key}] 자동 녹화 {'ON' if value else 'OFF'}")
        self._save_persistence()

    def set_channel_tags(self, composite_key: str, tags: list[str]) -> None:
        """채널의 태그를 지정한다."""
        task = self._channels.get(composite_key)
        if task is None:
            raise ValueError(f"채널 '{composite_key}'을(를) 찾을 수 없습니다.")
        task.tags = tags
        logger.info(f"[{composite_key}] 태그 변경: {tags}")
        self._save_persistence()

    def remove_tag_from_all_channels(self, tag_name: str) -> bool:
        """모든 채널에서 특정 태그를 일괄 제거한다."""
        modified_any = False
        for composite_key, task in self._channels.items():
            if tag_name in task.tags:
                task.tags.remove(tag_name)
                modified_any = True
        
        if modified_any:
            logger.info(f"모든 채널에서 태그 삭제: {tag_name}")
            self._save_persistence()
            
        return modified_any



    async def toggle_auto_record(self, composite_key: str) -> bool:
        """채널의 자동 녹화 설정을 토글한다.

        Returns:
            변경 후의 auto_record 값.
        """
        task = self._channels.get(composite_key)
        if task is None:
            raise ValueError(f"채널 '{composite_key}'을(를) 찾을 수 없습니다.")

        task.auto_record = not task.auto_record
        logger.info(f"[{composite_key}] 자동 녹화 {'ON' if task.auto_record else 'OFF'}")
        self._save_persistence()

        # 이미 라이브 중인데 auto_record를 ON으로 켰고 녹화가 안 되고 있으면 즉시 시작
        if (
            task.auto_record
            and task.is_live
            and task.platform != Platform.X_SPACES
            and (task.pipeline is None or task.pipeline.state != RecordingState.RECORDING)
        ):
            logger.info(f"[{composite_key}] 라이브 중 자동 녹화 ON → 즉시 녹화 시작")
            await self._start_recording(composite_key, channel_name=task.channel_name, title=task.title)

        return task.auto_record

    def trigger_scan_now(self, composite_key: Optional[str] = None) -> None:
        """채널 폴링 주기를 무시하고 즉시 스캔을 트리거한다.

        Args:
            composite_key: 특정 채널만 스캔. None이면 모든 채널.
        """
        if composite_key:
            event = self._scan_events.get(composite_key)
            if event:
                event.set()
                logger.info(f"[{composite_key}] 즉시 스캔 요청")
        else:
            for key, event in self._scan_events.items():
                event.set()
            logger.info(f"전체 채널 즉시 스캔 요청 ({len(self._scan_events)}개)")

    async def remove_channel(self, composite_key: str) -> None:
        """채널을 감시 목록에서 제거한다."""
        task = self._channels.pop(composite_key, None)
        if task is None:
            logger.warning(f"채널 '{composite_key}'을(를) 찾을 수 없습니다.")
            return

        # 녹화 중이면 파이프라인 정지
        pipe = task.pipeline
        if pipe is not None and pipe.state in (RecordingState.RECORDING, RecordingState.ERROR):
            logger.info(f"[{composite_key}] 채널 제거 전 녹화 정지 중...")
            await self._stop_recording(composite_key)

        # X Spaces 녹화 프로세스 종료
        if task.spaces_process is not None:
            await self._stop_spaces_recording(composite_key)

        # 감시 태스크 취소
        mt = task.monitor_task
        if mt is not None and not mt.done():
            mt.cancel()

        self._scan_events.pop(composite_key, None)
        logger.info(f"채널 제거: {composite_key}")
        self._save_persistence()

    async def start(self) -> None:
        """모든 등록된 채널의 감시를 시작한다."""
        if self._running:
            logger.warning("Conductor가 이미 실행 중입니다.")
            return

        self._running = True
        logger.info(f"Conductor 시작. 감시 채널 수: {self.channel_count}")

        for composite_key, task in self._channels.items():
            task.monitor_task = asyncio.create_task(
                self._monitor_channel(composite_key)
            )

        # 쿠키 검증 루프 시작
        self._cookie_check_task = asyncio.create_task(self._cookie_check_loop())
        # 녹화 통계 실시간 브로드캐스트 루프 시작
        self._stats_broadcast_task = asyncio.create_task(self._stats_broadcast_loop())

    async def stop(self) -> None:
        """모든 감시 및 녹화를 중지한다."""
        self._running = False
        logger.info("Conductor 종료 요청...")

        # 모든 이벤트 큐 종료 신호 전송
        self.broadcast_event("shutdown")

        # ── 1단계: 모든 monitor task를 먼저 취소 ─────────────────
        # retry sleep 중이거나 _start_recording 대기 중인 task가
        # 새 녹화를 시작하지 못하도록 recording stop보다 먼저 처리한다.
        for task in self._channels.values():
            mt = task.monitor_task
            if mt is not None and not mt.done():
                mt.cancel()

        if self._cookie_check_task is not None and not self._cookie_check_task.done():
            self._cookie_check_task.cancel()

        if self._stats_broadcast_task is not None and not self._stats_broadcast_task.done():
            self._stats_broadcast_task.cancel()

        # ── 2단계: 실행 중인 녹화 및 Spaces 프로세스 중지 ────────
        for composite_key, task in self._channels.items():
            pipe = task.pipeline
            if pipe is not None and pipe.state == RecordingState.RECORDING:
                await self._stop_recording(composite_key)

            if task.spaces_process is not None:
                await self._stop_spaces_recording(composite_key)

        logger.info("Conductor 종료 완료.")

    async def _stats_broadcast_loop(self) -> None:
        """녹화 중인 채널이 있을 때 2초마다 통계를 SSE로 브로드캐스트한다."""
        while self._running:
            await asyncio.sleep(2.0)
            any_recording = any(
                t.pipeline is not None and t.pipeline.state == RecordingState.RECORDING
                for t in self._channels.values()
            )
            if any_recording and self._event_queues:
                self.broadcast_event("status_update", self.get_all_status())

    async def _cookie_check_loop(self) -> None:
        """X 쿠키 유효성을 하루 1회 주기로 검증한다."""
        while self._running:
            try:
                # 마지막 검증 이후 24시간이 지났을 때만 실행
                now = datetime.now()
                if (
                    self._last_cookie_check is None
                    or (now - self._last_cookie_check).total_seconds() >= self._COOKIE_CHECK_INTERVAL
                ):
                    await self._check_x_cookie()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"쿠키 검증 루프 오류: {e}")

            # 1시간마다 깨어나서 24시간 경과 여부 확인
            await asyncio.sleep(3600)

    async def _check_x_cookie(self) -> None:
        """X 쿠키 유효성을 검증하고 만료 시 Discord 알림을 전송한다."""
        from app.engine.x_spaces import verify_cookie

        settings = get_settings()
        cookie_file = settings.x_cookie_file

        # X Spaces 채널이 없으면 검증 생략
        has_spaces = any(
            t.platform == Platform.X_SPACES for t in self._channels.values()
        )
        if not has_spaces:
            return

        if not cookie_file:
            self._cookie_status = {
                "valid": False,
                "checked_at": datetime.now().isoformat(),
                "reason": "쿠키 파일 경로가 설정되지 않았습니다.",
            }
            self._last_cookie_check = datetime.now()
            return

        logger.info("X 쿠키 유효성 검증 중...")
        result = await verify_cookie(cookie_file)
        prev_valid = self._cookie_status.get("valid", True)
        self._cookie_status = result
        self._last_cookie_check = datetime.now()

        if not result["valid"]:
            logger.warning(f"X 쿠키 만료 감지: {result.get('reason')}")
            # 이전에 유효했거나 처음 감지된 경우에만 알림 (반복 알림 방지)
            if prev_valid:
                self._notify(
                    NotificationKind.COOKIE_EXPIRED,
                    title="⚠️ X 쿠키 만료",
                    description=(
                        "X Spaces 쿠키가 만료되었습니다.\n"
                        "설정 페이지에서 쿠키 파일을 갱신해주세요."
                    ),
                    color="red",
                    fields={"이유": result.get("reason") or "알 수 없음"},
                )
        else:
            logger.info("X 쿠키 유효성 확인 완료: 정상")

    def get_cookie_status(self) -> dict:
        """X 쿠키 유효성 상태를 반환한다."""
        return dict(self._cookie_status)

    async def download_space(self, space_url: str) -> dict:
        """Space URL로 직접 다운로드한다.

        채널 등록 없이 space_url만으로 즉시 다운로드 가능.
        UserTweets API를 사용하지 않으므로 레이트 리밋 문제 없음.

        Args:
            space_url: X/Twitter Space URL (https://x.com/i/spaces/...)

        Returns:
            성공: {"started": True, "space_id": ..., "title": ..., "state": ..., "output": ...}
            실패: {"error": "오류 메시지"}
        """
        from app.engine.x_spaces import XSpacesEngine

        engine: XSpacesEngine = self._get_engine(Platform.X_SPACES)
        settings = get_settings()

        return await engine.download_by_space_url(
            space_url=space_url,
            output_dir=settings.download_dir,
            cookie_file=settings.x_cookie_file,
        )

    async def capture_space(self, username: str) -> dict:
        """X Spaces 채널의 m3u8 URL을 즉시 1회 조회한다.

        Discord /capture-space 커맨드에서 호출. 레이트 리밋 문제로 자동 폴링을
        비활성화한 대신 사용자가 원하는 시점에 수동으로 캡처를 트리거한다.

        Returns:
            {
                "captured": bool,
                "m3u8_url": str | None,
                "is_live": bool,
                "title": str | None,
                "channel_name": str | None,
            }
        """
        composite_key = self.make_composite_key(Platform.X_SPACES, username)
        task = self._channels.get(composite_key)

        if task is None:
            return {"captured": False, "m3u8_url": None, "is_live": False,
                    "title": None, "channel_name": None, "error": f"등록되지 않은 채널: {username}"}

        try:
            engine = self._get_engine(Platform.X_SPACES)
            status = await engine.check_live_status(username)
        except Exception as e:
            logger.error(f"[{composite_key}] capture_space 조회 실패: {e}")
            return {"captured": False, "m3u8_url": None, "is_live": False,
                    "title": None, "channel_name": None, "error": str(e)}

        # 상태 업데이트
        task.is_live = status["is_live"]
        task.channel_name = status.get("channel_name")
        task.title = status.get("title")
        task._current_space_id = status.get("space_id")

        new_m3u8 = status.get("m3u8_url")
        if new_m3u8:
            task.captured_m3u8_url = new_m3u8
            task.captured_m3u8_at = datetime.now().isoformat()
            self._save_persistence()
            logger.info(f"[{composite_key}] capture_space: m3u8 URL 캡처 완료")

        return {
            "captured": bool(new_m3u8),
            "m3u8_url": new_m3u8,
            "is_live": status["is_live"],
            "title": status.get("title"),
            "channel_name": status.get("channel_name"),
        }

    def _save_persistence(self) -> None:
        """채널 목록을 파일에 저장한다."""
        try:
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                key: {
                    "platform": t.platform.value,
                    "channel_id": t.channel_id,
                    "auto_record": t.auto_record,
                    "captured_m3u8_url": t.captured_m3u8_url,
                    "captured_m3u8_at": t.captured_m3u8_at,
                    "master_url": t.master_url,
                    "master_url_captured_at": t.master_url_captured_at,
                    "master_url_file": t.master_url_file,
                    "tags": t.tags,
                }
                for key, t in self._channels.items()
            }
            with open(self._persistence_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.debug(f"채널 목록 저장 완료: {self._persistence_path}")
            self.broadcast_event("status_update", self.get_all_status())
        except Exception as e:
            logger.error(f"채널 목록 저장 실패: {e}")

    # ── SSE 이벤트 Pub-Sub ─────────────────────────────────

    def add_event_queue(self, queue: asyncio.Queue) -> None:
        self._event_queues.append(queue)

    def remove_event_queue(self, queue: asyncio.Queue) -> None:
        if queue in self._event_queues:
            self._event_queues.remove(queue)

    def broadcast_event(self, event_type: str, data: Optional[dict | list] = None) -> None:
        if not self._event_queues:
            return
        payload = {"type": event_type}
        if data is not None:
            payload["data"] = data
        msg = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        for q in self._event_queues:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def _load_persistence(self) -> None:
        """파일에서 채널 목록을 로드한다.

        레거시 포맷(키에 ':' 없음)은 Chzzk 채널로 자동 마이그레이션한다.
        """
        if not self._persistence_path.exists():
            return

        try:
            with open(self._persistence_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            migrated = False
            for key, config in data.items():
                auto_record = config.get("auto_record", True)

                # 레거시 키 마이그레이션 (':'없는 키 = 구버전 Chzzk)
                if ":" not in key:
                    logger.info(f"레거시 채널 키 마이그레이션: '{key}' → 'chzzk:{key}'")
                    platform = Platform.CHZZK
                    channel_id = key
                    migrated = True
                else:
                    platform_str = config.get("platform", "chzzk")
                    try:
                        platform = Platform(platform_str)
                    except ValueError:
                        platform = Platform.CHZZK
                    channel_id = config.get("channel_id", key.split(":", 1)[-1])

                self.add_channel(channel_id, auto_record=auto_record, platform=platform)
                # m3u8 캡처 URL 복원
                composite_key_restored = self.make_composite_key(platform, channel_id)
                restored_task = self._channels.get(composite_key_restored)
                if restored_task:
                    if platform.value == "x_spaces":
                        restored_task.captured_m3u8_url = config.get("captured_m3u8_url")
                        restored_task.captured_m3u8_at = config.get("captured_m3u8_at")
                        restored_task.master_url = config.get("master_url")
                        restored_task.master_url_captured_at = config.get("master_url_captured_at")
                        restored_task.master_url_file = config.get("master_url_file")
                    if "tags" in config:
                        restored_task.tags = config.get("tags", [])

            if migrated:
                # 마이그레이션된 경우 새 포맷으로 즉시 저장
                self._save_persistence()
                logger.info("레거시 채널 데이터 마이그레이션 완료.")

            logger.info(f"채널 목록 로드 완료 ({len(data)}개): {self._persistence_path}")
        except Exception as e:
            logger.error(f"채널 목록 로드 실패: {e}")

    async def _monitor_channel(self, composite_key: str) -> None:
        """단일 채널의 라이브 상태를 주기적으로 확인한다."""
        settings = get_settings()
        task = self._channels.get(composite_key)

        # X Spaces는 레이트 리밋 방어를 위해 5분 폴링 간격 사용
        if task and task.platform == Platform.X_SPACES:
            interval = self._X_SPACES_POLL_INTERVAL
        else:
            interval = settings.monitor_interval
        retry_count = 0
        max_retries = settings.max_record_retries

        logger.info(f"[{composite_key}] 감시 시작 (주기: {interval}초)")

        while self._running:
            try:
                task = self._channels.get(composite_key)
                if task is None:
                    break

                engine = self._get_engine(task.platform)
                status = await engine.check_live_status(task.channel_id)

                was_live = task.is_live
                task.is_live = status["is_live"]
                task.last_error = None
                task.channel_name = status.get("channel_name")
                task.title = status.get("title")
                task.category = status.get("category")
                task.viewer_count = status.get("viewer_count", 0)
                task.thumbnail_url = status.get("thumbnail_url")
                task.profile_image_url = status.get("profile_image_url")

                # X Spaces: space_id, m3u8_url, master_url 업데이트
                if task.platform == Platform.X_SPACES:
                    task._current_space_id = status.get("space_id")
                    new_master = status.get("master_url")
                    new_m3u8 = status.get("m3u8_url")
                    # master URL이 새로 캡처되면 저장 (Space마다 1회)
                    if new_master and not task.master_url:
                        now_iso = datetime.now().isoformat()
                        task.master_url = new_master
                        task.master_url_captured_at = now_iso
                        task.captured_m3u8_url = new_m3u8
                        task.captured_m3u8_at = now_iso
                        # master URL을 파일로 저장 (녹화 실패 시 백업)
                        task.master_url_file = self._save_master_url_file(
                            task, new_master, task._current_space_id
                        )
                        logger.info(
                            f"[{composite_key}] 🎙️ Space master URL 캡처 완료 "
                            f"(space_id={task._current_space_id})"
                        )
                        self._save_persistence()
                        # 알림: master URL 캡처 + 자동 녹화 상태 안내
                        # (Master URL은 1024자를 넘을 수 있어 알림 계층에서 분할 전송한다)
                        rec_status = (
                            "🔴 자동 녹화 시작됨 (실시간 저장 중)"
                            if task.auto_record
                            else "⏸️ 자동 녹화 OFF — 아래 URL로 수동 다운로드 가능"
                        )
                        self._notify(
                            NotificationKind.SPACE_DETECTED,
                            title="🎙️ X Spaces 감지",
                            description=(
                                f"**@{task.channel_name or task.channel_id}** — "
                                f"{task.title or 'X Spaces'}\n{rec_status}"
                            ),
                            color="blue",
                            fields={
                                "Master URL": new_master,
                                "URL 파일": (
                                    f"`{task.master_url_file}`"
                                    if task.master_url_file
                                    else "저장 실패"
                                ),
                            },
                        )

                # ── 라이브 감지 날짜 기록 (하루 1회, 날짜 경계 자동 처리) ──
                if status["is_live"]:
                    today = datetime.now().strftime("%Y-%m-%d")
                    self._live_detections.setdefault(composite_key, set()).add(today)

                # ── 방송 시작 감지 ──
                if status["is_live"] and not was_live:
                    logger.info(
                        f"[{composite_key}] 🔴 방송 시작 감지! "
                        f"스트리머: {task.channel_name}, 제목: {task.title}"
                    )
                    # 감지 즉시 알림 — 녹화 준비(CDN 대기 5초 + yt-dlp 기동)를
                    # 기다리지 않는다. 녹화 결과는 별도 알림으로 이어진다.
                    # X Spaces는 위쪽 master URL 캡처 알림이 이 역할을 대신한다.
                    if task.platform != Platform.X_SPACES:
                        self._notify(
                            NotificationKind.LIVE_DETECTED,
                            title="🔴 방송 시작",
                            description=(
                                f"**{task.channel_name or task.channel_id}**\n"
                                f"{task.title or '제목 없음'}"
                            ),
                            color="green",
                            fields={
                                "플랫폼": task.platform.value,
                                "카테고리": task.category or "N/A",
                                "자동 녹화": "ON" if task.auto_record else "OFF",
                            },
                        )

                    if task.auto_record:
                        await self._start_recording(
                            composite_key,
                            channel_name=task.channel_name,
                            title=task.title,
                        )
                        retry_count = 0

                # ── 방송 종료 감지 ──
                elif not status["is_live"] and was_live:
                    logger.info(f"[{composite_key}] ⚫ 방송 종료 감지.")
                    # X Spaces: 다음 Space를 위해 master_url 초기화
                    if task.platform == Platform.X_SPACES:
                        task.master_url = None
                        task.master_url_captured_at = None
                        task.captured_m3u8_url = None
                        task.captured_m3u8_at = None
                        task.master_url_file = None
                        task._current_space_id = None
                        self._save_persistence()
                        logger.info(f"[{composite_key}] 🎙️ Space 종료 — master URL 초기화 완료.")
                    await self._stop_recording(composite_key)
                    retry_count = 0

                # ── 채팅 아카이빙 동적 시작 (Chzzk 전용, 녹화 중 설정이 켜진 경우) ──
                elif (
                    status["is_live"]
                    and task.platform == Platform.CHZZK
                    and task.pipeline is not None
                    and task.pipeline.state == RecordingState.RECORDING
                    and task.chat_archiver is None
                    and get_settings().chat_archive_enabled
                ):
                    try:
                        output_file = task.pipeline.get_status().get("output_path")
                        if output_file:
                            chat_file = Path(output_file).with_suffix(".jsonl")
                            archiver = ChatArchiver(
                                channel_id=task.channel_id,
                                output_path=chat_file,
                                auth=self._auth,
                            )
                            await archiver.start()
                            task.chat_archiver = archiver
                            logger.info(f"[{composite_key}] 채팅 아카이빙 동적 시작: {chat_file}")
                    except Exception as e:
                        logger.error(f"[{composite_key}] 채팅 아카이빙 동적 시작 실패: {e}")

                # ── 녹화 오류 시 자동 재시작 (Chzzk/TwitCasting 전용) ──
                elif status["is_live"] and task.auto_record and task.platform != Platform.X_SPACES:
                    pipe = task.pipeline
                    if pipe is not None and pipe.state in (RecordingState.ERROR, RecordingState.COMPLETED):
                        if retry_count < max_retries:
                            retry_count += 1
                            logger.warning(
                                f"[{composite_key}] 녹화 중단 감지. "
                                f"자동 재녹화 시도 ({retry_count}/{max_retries})..."
                            )
                            await asyncio.sleep(5)
                            if not self._running:
                                break
                            await self._start_recording(
                                composite_key,
                                channel_name=task.channel_name,
                                title=task.title,
                                is_retry=True,
                            )
                        elif retry_count == max_retries:
                            retry_count += 1
                            task.last_error = "최대 재시도 횟수 초과로 녹화 중단됨"
                            logger.error(
                                f"[{composite_key}] 최대 재시도 횟수 초과. "
                                f"녹화 시작 버튼으로 수동 재시작하세요."
                            )

            except asyncio.CancelledError:
                break
            except BaseException as e:
                task.last_error = f"감시 오류: {str(e)}"
                logger.error(f"[{composite_key}] 감시 오류: {e}", exc_info=e)

            # 폴링 대기 — 즉시 스캔 요청(trigger_scan_now) 시 event로 깨어남
            scan_event = self._scan_events.get(composite_key)
            if scan_event is not None:
                scan_event.clear()
                try:
                    await asyncio.wait_for(scan_event.wait(), timeout=float(interval))
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(interval)

    async def _stop_recording(self, composite_key: str) -> None:
        """채널의 녹화 및 채팅 아카이빙을 중지한다."""
        task = self._channels.get(composite_key)
        if task is None:
            return

        # X Spaces 녹화 중지
        if task.platform == Platform.X_SPACES:
            await self._stop_spaces_recording(composite_key)
            return

        # Chzzk/TwitCasting 파이프라인 중지
        pipe = task.pipeline
        if pipe is not None and pipe.state == RecordingState.RECORDING:
            await pipe.stop_recording()

            # ── 알림: 녹화 완료 ──
            status = pipe.get_status()
            duration = status.get("duration_seconds", 0) or 0
            output_file = status.get("output_file") or status.get("output_path") or "N/A"
            file_size = status.get("file_size_bytes", 0) / (1024 * 1024)
            duration_str = (
                f"{duration // 60:.0f}분 {duration % 60:.0f}초" if duration > 0 else "N/A"
            )
            self._notify(
                NotificationKind.RECORDING_COMPLETED,
                title="⏹ 녹화 완료",
                description=f"채널: **{task.channel_name or composite_key}**",
                color="blue",
                fields={
                    "녹화 시간": duration_str,
                    "파일 크기": f"{file_size:.1f} MB",
                    "저장 경로": str(output_file),
                },
            )

        # 녹화 완료 이력 저장
        if pipe is not None and pipe.state == RecordingState.COMPLETED:
            self._save_live_history(composite_key, task, pipe.get_status())

        # 채팅 아카이빙 중지
        archiver = task.chat_archiver
        if archiver is not None:
            try:
                await archiver.stop()
                task.chat_archiver = None
            except Exception as e:
                logger.error(f"[{composite_key}] 채팅 아카이빙 중지 실패: {e}")

        # 파이프라인 레퍼런스 정리 (모니터 루프의 의도치 않은 자동 재시작 방지)
        task.pipeline = None
        # 정지 후 프론트엔드에 즉시 상태 업데이트
        self.broadcast_event("status_update", self.get_all_status())

    async def _start_recording(
        self,
        composite_key: str,
        channel_name: Optional[str] = None,
        title: Optional[str] = None,
        is_retry: bool = False,
    ) -> None:
        """채널의 녹화를 시작한다."""
        task = self._channels.get(composite_key)
        if task is None:
            return

        # X Spaces는 별도 경로
        if task.platform == Platform.X_SPACES:
            await self._start_spaces_recording(composite_key, channel_name=channel_name, title=title)
            return

        try:
            settings = get_settings()
            quality = settings.recording_quality or "best"
            engine = self._get_engine(task.platform)
            live_url = engine.get_stream_url(task.channel_id)
            cookie_str = self._auth.get_ytdlp_cookies()

            # 최초 감지 시 CDN이 스트림 URL을 준비하는 시간을 확보
            if not is_retry:
                logger.debug(f"[{composite_key}] 스트림 CDN 준비 대기 (5초)...")
                await asyncio.sleep(5)
                if not self._running:
                    return

            pipeline = YtdlpLivePipeline(channel_id=task.channel_id)
            task.pipeline = pipeline

            await pipeline.start_recording(
                stream_obj=live_url,
                streamer_name=channel_name or task.channel_name,
                title=title or task.title,
                quality=quality,
                cookie_str=cookie_str,
            )
            logger.info(f"[{composite_key}] 자동 라이브 녹화 시작 (quality={quality}).")

            # ── 알림: 녹화 시작 (재시도 시엔 생략) ──
            if not is_retry:
                self._notify(
                    NotificationKind.RECORDING_STARTED,
                    title="🎬 녹화 시작",
                    description=(
                        f"채널: **{channel_name or composite_key}**\n제목: {title or 'N/A'}"
                    ),
                    color="green",
                    fields={"화질": quality, "플랫폼": task.platform.value},
                )

            # ── 채팅 아카이빙 시작 (Chzzk 전용) ──
            if task.platform == Platform.CHZZK and settings.chat_archive_enabled:
                try:
                    recording_status = pipeline.get_status()
                    output_file = recording_status.get("output_path")
                    if output_file:
                        chat_file = Path(output_file).with_suffix(".jsonl")
                        archiver = ChatArchiver(
                            channel_id=task.channel_id,
                            output_path=chat_file,
                            auth=self._auth,
                        )
                        await archiver.start()
                        task.chat_archiver = archiver
                        logger.info(f"[{composite_key}] 채팅 아카이빙 시작: {chat_file}")
                except Exception as e:
                    logger.error(f"[{composite_key}] 채팅 아카이빙 시작 실패: {e}")
        except Exception as e:
            task.last_error = f"녹화 시작 오류: {str(e)}"
            logger.error(f"[{composite_key}] 녹화 시작 실패: {e}")

            self._notify(
                NotificationKind.RECORDING_FAILED,
                title="❌ 녹화 시작 실패",
                description=f"채널: **{channel_name or composite_key}**\n오류: {str(e)}",
                color="red",
            )

        # 녹화 시작/실패 후 프론트엔드에 즉시 상태 업데이트
        self.broadcast_event("status_update", self.get_all_status())

    async def _start_spaces_recording(
        self,
        composite_key: str,
        channel_name: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        """X Spaces를 yt-dlp subprocess로 녹화 시작한다."""
        task = self._channels.get(composite_key)
        if task is None:
            return
        if task._current_space_id is None:
            logger.error(f"[{composite_key}] Space ID 없음. 녹화 불가.")
            return

        try:
            from app.engine.x_spaces import XSpacesEngine
            engine: XSpacesEngine = self._get_engine(Platform.X_SPACES)

            settings = get_settings()
            process, output_path = await engine.start_ytdlp_recording(
                space_id=task._current_space_id,
                output_dir=settings.download_dir,
                channel_name=channel_name or task.channel_name or task.channel_id,
                title=title or task.title,
                cookie_file=settings.x_cookie_file,
            )
            task.spaces_process = process
            task.spaces_output_path = output_path
            logger.info(f"[{composite_key}] X Spaces 녹화 시작 (space_id={task._current_space_id}).")

            self._notify(
                NotificationKind.RECORDING_STARTED,
                title="🎬 Spaces 녹화 시작",
                description=(
                    f"채널: **{channel_name or composite_key}**\n제목: {title or 'N/A'}"
                ),
                color="green",
                fields={"플랫폼": "X Spaces"},
            )
        except Exception as e:
            task.last_error = f"Spaces 녹화 오류: {str(e)}"
            logger.error(f"[{composite_key}] Spaces 녹화 시작 실패: {e}")
            self._notify(
                NotificationKind.RECORDING_FAILED,
                title="❌ Spaces 녹화 시작 실패",
                description=f"채널: **{channel_name or composite_key}**\n오류: {str(e)}",
                color="red",
            )

        # 녹화 시작/실패 후 프론트엔드에 즉시 상태 업데이트
        self.broadcast_event("status_update", self.get_all_status())

    def _save_master_url_file(
        self,
        task: "ChannelTask",
        master_url: str,
        space_id: Optional[str],
    ) -> Optional[str]:
        """master URL을 .txt 파일로 저장하고 파일 경로를 반환한다.

        녹화가 실패하더라도 나중에 수동으로 다운로드할 수 있도록 백업용으로 저장한다.
        저장 위치: {download_dir}/x_spaces_urls/{channel}_{space_id}_{datetime}.txt
        """
        try:
            settings = get_settings()
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            channel_name = task.channel_name or task.channel_id
            safe_name = "".join(c for c in channel_name if c.isalnum() or c in "-_@")
            sid = (space_id or "unknown")[:20]
            filename = f"{safe_name}_{sid}_{now_str}.txt"

            url_dir = Path(settings.download_dir) / "x_spaces_urls"
            url_dir.mkdir(parents=True, exist_ok=True)
            file_path = url_dir / filename

            content = (
                f"X Spaces Master URL\n"
                f"{'=' * 50}\n"
                f"채널: @{channel_name}\n"
                f"제목: {task.title or 'N/A'}\n"
                f"Space ID: {space_id or 'unknown'}\n"
                f"캡처 시각: {now_str}\n"
                f"\nMaster URL (안정적, ~30일 유효):\n{master_url}\n"
                f"\n다운로드 방법:\n"
                f"  yt-dlp \"{master_url}\" -o \"{channel_name}_%(title)s.%(ext)s\"\n"
            )
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"[{task.channel_id}] 🗂️ Master URL 파일 저장: {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"[{task.channel_id}] Master URL 파일 저장 실패: {e}")
            return None

    async def _stop_spaces_recording(self, composite_key: str) -> None:
        """X Spaces yt-dlp 프로세스를 종료한다."""
        task = self._channels.get(composite_key)
        if task is None or task.spaces_process is None:
            return

        proc = task.spaces_process
        output_path = task.spaces_output_path
        try:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    proc.kill()
            task.spaces_process = None
            task.spaces_output_path = None
            task._current_space_id = None
            logger.info(f"[{composite_key}] Spaces 녹화 중지.")

            # yt-dlp가 SIGTERM으로 종료되면 .part 파일이 남을 수 있음 → rename
            if output_path:
                part_file = Path(output_path + ".part")
                final_file = Path(output_path)
                if part_file.exists() and not final_file.exists():
                    part_file.rename(final_file)
                    logger.info(f"[{composite_key}] .part 파일 rename 완료: {final_file.name}")
        except Exception as e:
            logger.error(f"[{composite_key}] Spaces 녹화 중지 실패: {e}")

        # 정지 후 프론트엔드에 즉시 상태 업데이트
        self.broadcast_event("status_update", self.get_all_status())

    async def start_manual_recording(self, composite_key: str) -> dict:
        """수동으로 특정 채널의 녹화를 시작한다."""
        task = self._channels.get(composite_key)
        if task is None:
            # 미등록 채널 처리: 레거시 호환 (Chzzk 채널로 처리)
            platform, channel_id = self.parse_composite_key(composite_key)
            task = ChannelTask(
                channel_id=channel_id,
                platform=platform,
                auto_record=False,
            )
            self._channels[composite_key] = task

        pipe = task.pipeline
        if pipe is not None and pipe.state == RecordingState.RECORDING:
            return {"error": "이미 녹화 중입니다.", **pipe.get_status()}

        # 수동 녹화 시에도 상태 정보 업데이트 시도
        try:
            engine = self._get_engine(task.platform)
            status = await engine.check_live_status(task.channel_id)
            task.channel_name = status.get("channel_name")
            task.title = status.get("title")
            if task.platform == Platform.X_SPACES:
                task._current_space_id = status.get("space_id")
        except Exception:
            pass

        await self._start_recording(composite_key)

        if task.platform == Platform.X_SPACES:
            return {"message": "Spaces 녹화 시작됨.", "space_id": task._current_space_id}

        pipe = task.pipeline
        if pipe is not None:
            return pipe.get_status()
        return {"error": "녹화 시작 실패."}

    async def stop_manual_recording(self, composite_key: str) -> dict:
        """수동으로 특정 채널의 녹화를 중지한다."""
        task = self._channels.get(composite_key)
        if task is None:
            return {"error": "녹화 중인 채널이 아닙니다."}

        if task.platform == Platform.X_SPACES:
            await self._stop_spaces_recording(composite_key)
            return {"message": "Spaces 녹화 중지됨."}

        pipe = task.pipeline
        if pipe is None:
            return {"error": "녹화 중인 채널이 아닙니다."}

        await self._stop_recording(composite_key)
        return pipe.get_status()

    async def stop_all_recordings(self) -> dict:
        """현재 진행 중인 모든 채널의 녹화를 중지한다."""
        stopped_count = 0
        for composite_key, task in list(self._channels.items()):
            if task.platform == Platform.X_SPACES and task.spaces_process is not None:
                await self._stop_spaces_recording(composite_key)
                stopped_count += 1
            elif task.pipeline is not None and task.pipeline.state == RecordingState.RECORDING:
                await self._stop_recording(composite_key)
                stopped_count += 1

        return {"stopped_count": stopped_count, "message": f"{stopped_count}개의 채널 녹화를 중지했습니다."}

    def get_all_status(self) -> list[dict]:
        """모든 채널의 상태를 반환한다."""
        result: list[dict] = []
        for composite_key, task in self._channels.items():
            status: dict = {
                "composite_key": composite_key,
                "platform": task.platform.value,
                "channel_id": task.channel_id,
                "auto_record": task.auto_record,
                "is_live": task.is_live,
                "recording": None,
                "chat_archiving": None,
                "channel_name": task.channel_name,
                "title": task.title,
                "category": task.category,
                "viewer_count": task.viewer_count,
                "thumbnail_url": task.thumbnail_url,
                "profile_image_url": task.profile_image_url,
                "tags": getattr(task, "tags", []),
                "last_error": getattr(task, "last_error", None),
            }
            pipe = task.pipeline
            if pipe is not None:
                status["recording"] = pipe.get_status()

            if task.spaces_process is not None:
                status["recording"] = {
                    "is_recording": True,
                    "state": "recording",
                    "platform": "x_spaces",
                    "space_id": task._current_space_id,
                }

            # X Spaces URL 캡처 정보
            if task.platform == Platform.X_SPACES:
                status["master_url"] = task.master_url
                status["master_url_captured_at"] = task.master_url_captured_at
                status["master_url_file"] = task.master_url_file
                status["captured_m3u8_url"] = task.captured_m3u8_url
                status["captured_m3u8_at"] = task.captured_m3u8_at

            archiver = task.chat_archiver
            if archiver is not None:
                status["chat_archiving"] = archiver.get_status()

            result.append(status)
        return result

    # ── 라이브 이력 관리 ─────────────────────────────────────

    def _save_live_history(self, composite_key: str, task: ChannelTask, pipe_status: dict) -> None:
        """라이브 녹화 완료 이력을 JSON 파일에 저장한다."""
        try:
            self._live_history_path.parent.mkdir(parents=True, exist_ok=True)
            history: list[dict] = []
            if self._live_history_path.exists():
                with open(self._live_history_path, "r", encoding="utf-8") as f:
                    history = json.load(f)

            history.append({
                "composite_key": composite_key,
                "platform": task.platform.value,
                "channel_id": task.channel_id,
                "channel_name": task.channel_name or task.channel_id,
                "started_at": pipe_status.get("start_time"),
                "ended_at": datetime.now().isoformat(),
                "duration_seconds": pipe_status.get("duration_seconds", 0),
                "file_size_bytes": pipe_status.get("file_size_bytes", 0),
                "output_path": pipe_status.get("output_path"),
            })

            with open(self._live_history_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            logger.debug(f"[{composite_key}] 라이브 이력 저장 완료.")
        except Exception as e:
            logger.error(f"[{composite_key}] 라이브 이력 저장 실패: {e}")

    def get_live_history(self) -> list[dict]:
        """저장된 라이브 녹화 이력을 반환한다."""
        if not self._live_history_path.exists():
            return []
        try:
            with open(self._live_history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def get_live_detections(self) -> dict[str, int]:
        """채널별 라이브 감지 횟수를 반환한다 (최근 30일 기준, 하루 1회 카운트).

        Returns:
            { composite_key: 최근 30일 내 감지된 날짜 수 }
        """
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        return {
            key: sum(1 for d in dates if d >= cutoff)
            for key, dates in self._live_detections.items()
        }
