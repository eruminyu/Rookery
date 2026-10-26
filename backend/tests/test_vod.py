"""
test_vod.py
VodDownloadTask 상태 전이, 취소/일시정지/재개 플래그, reorder_tasks(), clear_completed_tasks() 테스트
"""

import asyncio
from pathlib import Path

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from app.engine.vod import VodDownloadState, VodDownloadTask, VodEngine


class TestVodDownloadIdentity:
    @pytest.fixture(autouse=True)
    def mock_ffmpeg_location(self):
        # 단일 파일 복사 검증에는 FFmpeg 실행이 필요하지 않다.
        with patch("app.core.config.Settings.resolve_ffmpeg_path", return_value="ffmpeg"):
            yield

    @pytest.mark.asyncio
    @pytest.mark.parametrize("concurrent", [False, True])
    async def test_same_title_downloads_distinct_videos(self, tmp_path, monkeypatch, concurrent):
        """같은 제목의 기존 파일이 있어도 각 영상의 실제 바이트를 따로 저장해야 한다."""
        import yt_dlp

        engine = VodEngine()
        output_dir = tmp_path / "downloads"
        output_dir.mkdir()
        legacy_file = output_dir / "[Channel] Same title.mp4"
        legacy_file.write_bytes(b"previous download")
        tasks = []
        metadata = {}
        payloads = [b"first video content", b"second video content"]
        for video_id, payload in zip(("100", "200"), payloads):
            source = tmp_path / f"source-{video_id}.mp4"
            source.write_bytes(payload)
            task = VodDownloadTask(
                url=f"https://chzzk.naver.com/video/{video_id}",
                output_dir=str(output_dir),
            )
            tasks.append(task)
            engine._tasks[task.task_id] = task
            metadata[task.url] = {
                "id": video_id,
                "title": "Same title",
                "uploader": "Channel",
                "extractor": "chzzk:video",
                "extractor_key": "CHZZKVideo",
                "ext": "mp4",
                "url": source.as_uri(),
                "webpage_url": task.url,
            }

        # 사이트 메타데이터만 대체하고 실제 yt-dlp의 파일 존재 판정과 다운로드를 실행한다.
        def extract_info(ydl, url, download=True):
            info = metadata[url].copy()
            return ydl.process_ie_result(info, download=True) if download else info

        build_options = engine._build_ytdlp_options

        def local_options(*args, **kwargs):
            return {**build_options(*args, **kwargs), "enable_file_urls": True}

        monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)
        monkeypatch.setattr(engine, "_build_ytdlp_options", local_options)
        if concurrent:
            await asyncio.gather(*(engine._download_external(t.task_id, t) for t in tasks))
        else:
            for task in tasks:
                await engine._download_external(task.task_id, task)

        assert tasks[0].output_path != tasks[1].output_path
        for task, payload in zip(tasks, payloads):
            assert task.state == VodDownloadState.COMPLETED
            assert Path(task.output_path).read_bytes() == payload
            assert task.expected_part_file == task.output_path + ".part"
        assert legacy_file.read_bytes() == b"previous download"

    def test_filename_identity_is_stable_and_scoped_to_extractor(self, tmp_path):
        """같은 영상은 재개 경로를 유지하고, 사이트가 다르면 같은 ID도 구분한다."""
        import yt_dlp

        engine = VodEngine()
        task = VodDownloadTask(output_dir=str(tmp_path))
        info = {
            "id": "12345", "title": "Same title", "uploader": "Channel",
            "extractor_key": "CHZZKVideo", "ext": "mp4",
        }
        with yt_dlp.YoutubeDL(engine._build_ytdlp_options(task)) as ydl:
            filename = ydl.prepare_filename(info)
            assert ydl.prepare_filename(info.copy()) == filename
            assert ydl.prepare_filename({**info, "extractor_key": "Youtube"}) != filename


class TestVodDownloadState:
    """VodDownloadState Enum 테스트"""

    def test_all_states_exist(self):
        """모든 상태가 정의되어 있는지 확인"""
        assert VodDownloadState.IDLE == "idle"
        assert VodDownloadState.DOWNLOADING == "downloading"
        assert VodDownloadState.PAUSED == "paused"
        assert VodDownloadState.COMPLETED == "completed"
        assert VodDownloadState.ERROR == "error"
        assert VodDownloadState.CANCELLING == "cancelling"


class TestVodDownloadTask:
    """VodDownloadTask 데이터 클래스 테스트"""

    def test_default_values(self):
        """기본값 확인"""
        task = VodDownloadTask()

        assert task.url == ""
        assert task.title == "Unknown"
        assert task.state == VodDownloadState.IDLE
        assert task.progress == 0.0
        assert task.quality == "best"
        assert task.output_path is None
        assert task.error_message is None
        assert task.download_speed == 0.0
        assert task.downloaded_bytes == 0
        assert task.total_bytes == 0
        assert task.eta_seconds == 0
        assert task.retry_count == 0
        assert task.max_retries == 3

    def test_task_id_auto_generation(self):
        """task_id가 자동 생성되는지 확인"""
        task1 = VodDownloadTask()
        task2 = VodDownloadTask()

        assert task1.task_id != task2.task_id
        assert len(task1.task_id) > 0

    def test_pause_event_initial_state(self):
        """pause_event 초기 상태 (일시정지 아님)"""
        task = VodDownloadTask()

        assert task.pause_event.is_set() is True  # set = 재생 중 (일시정지 아님)

    def test_cancel_flag_initial_state(self):
        """cancel_flag 초기 상태 (취소 아님)"""
        task = VodDownloadTask()

        assert task.cancel_flag is False

    def test_state_transitions(self):
        """상태 전이"""
        task = VodDownloadTask()

        # IDLE → DOWNLOADING
        task.state = VodDownloadState.DOWNLOADING
        assert task.state == VodDownloadState.DOWNLOADING

        # DOWNLOADING → PAUSED
        task.state = VodDownloadState.PAUSED
        assert task.state == VodDownloadState.PAUSED

        # PAUSED → DOWNLOADING
        task.state = VodDownloadState.DOWNLOADING
        assert task.state == VodDownloadState.DOWNLOADING

        # DOWNLOADING → COMPLETED
        task.state = VodDownloadState.COMPLETED
        assert task.state == VodDownloadState.COMPLETED

    def test_state_transition_to_error(self):
        """ERROR 상태 전이"""
        task = VodDownloadTask()

        task.state = VodDownloadState.ERROR
        task.error_message = "Download failed"

        assert task.state == VodDownloadState.ERROR
        assert task.error_message == "Download failed"

    def test_progress_update(self):
        """진행률 업데이트"""
        task = VodDownloadTask()

        task.progress = 25.5
        assert task.progress == 25.5

        task.progress = 100.0
        assert task.progress == 100.0

    def test_timestamps(self):
        """생성/시작/완료 타임스탬프"""
        task = VodDownloadTask()

        assert isinstance(task.created_at, datetime)
        assert task.started_at is None
        assert task.completed_at is None

        # 시작 시간 설정
        task.started_at = datetime.now()
        assert task.started_at is not None

        # 완료 시간 설정
        task.completed_at = datetime.now()
        assert task.completed_at is not None


class TestVodEngine:
    """VodEngine 클래스 테스트"""

    @pytest.fixture
    def mock_engine(self, tmp_path):
        """
        VodEngine 인스턴스를 생성하되, history 파일 경로를 임시 경로로 패치합니다.
        데이터 격리를 위해 모든 테스트 메서드에서 이 fixture를 사용하거나
        개별적으로 패치해야 합니다.
        """
        # 가짜 history 파일 경로
        history_file = tmp_path / "vod_history.json"
        
        # Path("data/vod_history.json") 호출을 가로채서 임시 경로로 리다이렉트
        # 주의: app.engine.vod 모듈 내부의 Path를 패치해야 함
        with patch("app.engine.vod.Path") as mock_path_cls:
            # Path(...) 생성자가 호출될 때, 실제 Path 객체(임시 경로)를 반환하도록 설정
            # side_effect를 사용하여 입력값에 따라 다른 동작을 하게 할 수도 있으나,
            # 여기서는 간단히 모든 Path 생성을 임시 경로 처리하거나, 
            # 특정 경로만 바꿔치기 하는 로직이 필요할 수 있음.
            # 하지만 가장 확실한 방법은 _history_file 속성을 덮어쓰는 것보다
            # __init__ 실행 시점의 Path를 제어하는 것임.
            
            # 더 간단한 방법: 인스턴스 생성 후 _history_file 교체는 _load_history가 이미 실행된 후라 늦음.
            # 따라서 app.engine.vod.Path를 Mock으로 감싸서 특정 경로 요청만 바꿔치기함.
            
            def side_effect(path_str):
                if str(path_str) == "data/vod_history.json":
                    return history_file
                return type(tmp_path)(path_str)  # 나머지는 정상 처리 (pathlib.Path 동작 모사)

            mock_path_cls.side_effect = side_effect
            
            engine = VodEngine()
            return engine

    def test_initial_state(self, mock_engine):
        """초기 상태 확인"""
        engine = mock_engine

        # 작업이 없으면 IDLE 상태 반환
        assert engine.state == VodDownloadState.IDLE
        assert engine.progress == 0.0

    def test_is_chzzk_url(self, mock_engine):
        """치지직 URL 검증"""
        engine = mock_engine

        # 치지직 URL
        assert engine._is_chzzk_url("https://chzzk.naver.com/video/12345") is True
        assert engine._is_chzzk_url("https://chzzk.naver.com/live/abc") is True

        # 비치지직 URL
        assert engine._is_chzzk_url("https://youtube.com/watch?v=123") is False
        assert engine._is_chzzk_url("https://twitch.tv/streamer") is False

    def test_list_all_tasks_empty(self, mock_engine):
        """작업이 없는 경우 빈 리스트 반환"""
        engine = mock_engine

        tasks = engine.list_all_tasks()

        assert tasks == []

    def test_get_task_status_not_found(self, mock_engine):
        """존재하지 않는 task_id 조회 시 예외"""
        engine = mock_engine

        status = engine.get_task_status("nonexistent_task_id")

        assert status["error"] is not None

    def test_cancel_download_not_found(self, mock_engine):
        """존재하지 않는 task_id 취소 시도"""
        engine = mock_engine

        result = engine.cancel_download("nonexistent_task_id")

        assert "error" in result or "message" in result

    def test_pause_download_not_found(self, mock_engine):
        """존재하지 않는 task_id 일시정지 시도"""
        engine = mock_engine

        result = engine.pause_download("nonexistent_task_id")

        assert "error" in result or "message" in result

    def test_resume_download_not_found(self, mock_engine):
        """존재하지 않는 task_id 재개 시도"""
        engine = mock_engine

        result = engine.resume_download("nonexistent_task_id")

        assert "error" in result or "message" in result

    def test_reorder_tasks_empty(self, mock_engine):
        """빈 작업 목록 재정렬"""
        engine = mock_engine

        result = engine.reorder_tasks([])

        assert result["message"] is not None
        assert result["count"] == 0

    def test_reorder_tasks_with_mock_tasks(self, mock_engine):
        """모의 작업을 사용한 재정렬 테스트"""
        engine = mock_engine

        # 작업 추가 (실제 다운로드는 하지 않음)
        task1 = VodDownloadTask(url="https://example.com/1", title="Task 1")
        task2 = VodDownloadTask(url="https://example.com/2", title="Task 2")
        task3 = VodDownloadTask(url="https://example.com/3", title="Task 3")

        engine._tasks[task1.task_id] = task1
        engine._tasks[task2.task_id] = task2
        engine._tasks[task3.task_id] = task3

        # 재정렬: task3, task1, task2
        new_order = [task3.task_id, task1.task_id, task2.task_id]
        result = engine.reorder_tasks(new_order)

        assert result["count"] == 3

        # 재정렬된 순서 확인
        tasks_list = engine.list_all_tasks()
        assert tasks_list[0]["task_id"] == task3.task_id
        assert tasks_list[1]["task_id"] == task1.task_id
        assert tasks_list[2]["task_id"] == task2.task_id

    def test_clear_completed_tasks_empty(self, mock_engine):
        """완료된 작업이 없는 경우"""
        engine = mock_engine

        result = engine.clear_completed_tasks()

        assert result["deleted_count"] == 0

    def test_clear_completed_tasks_with_completed(self, mock_engine):
        """완료된 작업 삭제 테스트"""
        engine = mock_engine

        # 완료된 작업 추가
        task1 = VodDownloadTask(url="https://example.com/1", title="Task 1", state=VodDownloadState.COMPLETED)
        task2 = VodDownloadTask(url="https://example.com/2", title="Task 2", state=VodDownloadState.DOWNLOADING)
        task3 = VodDownloadTask(url="https://example.com/3", title="Task 3", state=VodDownloadState.COMPLETED)

        engine._tasks[task1.task_id] = task1
        engine._tasks[task2.task_id] = task2
        engine._tasks[task3.task_id] = task3

        result = engine.clear_completed_tasks()

        assert result["deleted_count"] == 2
        assert result["remaining_count"] == 1

        # 남은 작업 확인
        tasks_list = engine.list_all_tasks()
        assert len(tasks_list) == 1
        assert tasks_list[0]["task_id"] == task2.task_id

    def test_get_status_with_tasks(self, mock_engine):
        """작업이 있는 경우 전체 상태 조회"""
        engine = mock_engine

        # 작업 추가
        task1 = VodDownloadTask(url="https://example.com/1", title="Task 1", state=VodDownloadState.DOWNLOADING)
        task2 = VodDownloadTask(url="https://example.com/2", title="Task 2", state=VodDownloadState.COMPLETED)

        engine._tasks[task1.task_id] = task1
        engine._tasks[task2.task_id] = task2

        status = engine.get_status()

        # 첫 번째 작업의 상태 반환
        assert status["state"] == "downloading"
        assert status["progress"] >= 0.0


class TestTwitcastingDownloads:
    """로그인 전용 TwitCasting 아카이브는 재시도 없이 이유를 알려야 한다."""

    URL = "https://twitcasting.tv/c:s2s2rete/movie/841067169"
    M3U8_ERROR = "ERROR: [TwitCasting] 841067169: Failed to get m3u8 playlist; please report this issue"
    TIMEOUT_ERROR = "ERROR: Unable to download webpage: timed out"
    COOKIES = (
        "# Netscape HTTP Cookie File\n"
        ".twitcasting.tv\tTRUE\t/\tTRUE\t1790000000\ttc_ss\tsession-value\n"
    )

    @pytest.fixture(autouse=True)
    def mock_ffmpeg_location(self):
        with patch("app.core.config.Settings.resolve_ffmpeg_path", return_value="ffmpeg"):
            yield

    @pytest.fixture
    def retry_sleep(self, monkeypatch):
        # 재시도 백오프(3초, 6초)를 기다리지 않고 몇 번 쉬었는지만 센다.
        sleep = AsyncMock()
        monkeypatch.setattr("app.engine.vod.asyncio.sleep", sleep)
        return sleep

    def _add_task(self, engine, tmp_path, url=None):
        task = VodDownloadTask(url=url or self.URL, output_dir=str(tmp_path))
        engine._tasks[task.task_id] = task
        return task

    def _fail_extraction(self, monkeypatch, message):
        import yt_dlp

        seen = []

        def extract_info(ydl, url, download=True):
            cookie_file = ydl.params.get("cookiefile")
            seen.append((cookie_file, Path(cookie_file).read_text(encoding="utf-8") if cookie_file else None))
            raise yt_dlp.utils.DownloadError(message)

        monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)
        return seen

    @pytest.mark.asyncio
    async def test_login_only_archive_fails_once_with_reason(self, tmp_path, monkeypatch, retry_sleep):
        engine = VodEngine()
        task = self._add_task(engine, tmp_path)
        seen = self._fail_extraction(monkeypatch, self.M3U8_ERROR)
        reason = "로그인한 사용자만 볼 수 있는 TwitCasting 영상이라 받을 수 없습니다."
        explain = AsyncMock(return_value=reason)
        monkeypatch.setattr("app.engine.vod.explain_unplayable", explain)

        await engine._run_download(task.task_id)

        assert task.state == VodDownloadState.ERROR
        assert task.error_message == reason
        assert len(seen) == 1
        retry_sleep.assert_not_awaited()
        explain.assert_awaited_once_with(self.URL, self.M3U8_ERROR, has_cookies=False)

    @pytest.mark.asyncio
    async def test_other_failures_still_retry(self, tmp_path, monkeypatch, retry_sleep):
        engine = VodEngine()
        task = self._add_task(engine, tmp_path)
        seen = self._fail_extraction(monkeypatch, self.TIMEOUT_ERROR)
        monkeypatch.setattr("app.engine.vod.explain_unplayable", AsyncMock(return_value=None))

        # 동시 개수는 로컬 .env를 따른다. 재시도가 다시 슬롯을 붙잡으면 멈추지 말고 실패해야 한다.
        await asyncio.wait_for(engine._run_download(task.task_id), timeout=5)

        assert task.state == VodDownloadState.ERROR
        assert len(seen) == task.max_retries
        assert retry_sleep.await_count == task.max_retries - 1

    @pytest.mark.asyncio
    async def test_retry_with_single_slot_finishes(self, tmp_path, monkeypatch, retry_sleep):
        from app.core.config import get_settings

        # asyncio.Semaphore는 재진입되지 않는다. 슬롯이 하나뿐일 때 재시도가 쥔 슬롯을
        # 놓지 않고 다시 얻으려 하면 자기 자신을 기다리며 DOWNLOADING에 영원히 머문다.
        get_settings().vod_max_concurrent = 1
        engine = VodEngine()
        task = self._add_task(engine, tmp_path)
        seen = self._fail_extraction(monkeypatch, self.TIMEOUT_ERROR)
        monkeypatch.setattr("app.engine.vod.explain_unplayable", AsyncMock(return_value=None))
        slot_held_during_backoff = []
        retry_sleep.side_effect = lambda _delay: slot_held_during_backoff.append(engine._semaphore.locked())

        await asyncio.wait_for(engine._run_download(task.task_id), timeout=5)

        assert task.state == VodDownloadState.ERROR
        assert task.error_message == f"재시도 {task.max_retries}회 실패: {self.TIMEOUT_ERROR}"
        assert len(seen) == task.max_retries
        # 백오프 간격은 그대로 두되, 기다리는 동안에는 대기 중인 다른 다운로드가 슬롯을 쓸 수 있어야 한다.
        assert [c.args[0] for c in retry_sleep.await_args_list] == [3, 6]
        assert slot_held_during_backoff == [False, False]
        assert not engine._semaphore.locked()

    @pytest.mark.asyncio
    async def test_simultaneous_failures_do_not_deadlock(self, tmp_path, monkeypatch, retry_sleep):
        from app.core.config import get_settings

        # 슬롯을 다 채운 작업이 한꺼번에 실패하면, 각자 슬롯을 쥔 채 남은 슬롯을 기다리며 교착될 수 있다.
        get_settings().vod_max_concurrent = 3
        engine = VodEngine()
        tasks = [self._add_task(engine, tmp_path) for _ in range(3)]
        seen = self._fail_extraction(monkeypatch, self.TIMEOUT_ERROR)
        monkeypatch.setattr("app.engine.vod.explain_unplayable", AsyncMock(return_value=None))

        await asyncio.wait_for(
            asyncio.gather(*(engine._run_download(t.task_id) for t in tasks)), timeout=5
        )

        assert all(t.state == VodDownloadState.ERROR for t in tasks)
        assert all(t.retry_count == t.max_retries for t in tasks)
        assert len(seen) == len(tasks) * tasks[0].max_retries

    @pytest.mark.asyncio
    async def test_cookie_copy_is_lent_to_twitcasting(self, tmp_path, monkeypatch):
        import yt_dlp
        from app.core.config import get_settings

        original = tmp_path / "twitcasting_cookies.txt"
        original.write_text(self.COOKIES, encoding="utf-8")
        get_settings().twitcasting_cookie_file = str(original)
        engine = VodEngine()
        task = self._add_task(engine, tmp_path)
        seen = self._fail_extraction(monkeypatch, "ERROR: boom")
        explain = AsyncMock(return_value=None)
        monkeypatch.setattr("app.engine.vod.explain_unplayable", explain)

        with pytest.raises(yt_dlp.utils.DownloadError):
            await engine._download_external(task.task_id, task)

        lent, content = seen[0]
        assert lent is not None and lent != str(original)
        assert content == self.COOKIES
        assert not Path(lent).exists()
        assert original.read_text(encoding="utf-8") == self.COOKIES
        explain.assert_awaited_once_with(self.URL, "ERROR: boom", has_cookies=True)

    @pytest.mark.asyncio
    async def test_other_sites_get_no_twitcasting_cookie(self, tmp_path, monkeypatch):
        import yt_dlp
        from app.core.config import get_settings

        original = tmp_path / "twitcasting_cookies.txt"
        original.write_text(self.COOKIES, encoding="utf-8")
        get_settings().twitcasting_cookie_file = str(original)
        engine = VodEngine()
        task = self._add_task(engine, tmp_path, url="https://www.youtube.com/watch?v=abc")
        seen = self._fail_extraction(monkeypatch, "ERROR: boom")
        explain = AsyncMock(return_value=None)
        monkeypatch.setattr("app.engine.vod.explain_unplayable", explain)

        with pytest.raises(yt_dlp.utils.DownloadError):
            await engine._download_external(task.task_id, task)

        assert seen[0] == (None, None)
        explain.assert_not_awaited()


class TestChzzkHlsInitMapPatch:
    """치지직 liveRewindPlaybackJson 기반 HLS의 중복 #EXT-X-MAP 처리 테스트."""

    @pytest.fixture(autouse=True)
    def mock_ffmpeg_location(self):
        with patch("app.core.config.Settings.resolve_ffmpeg_path", return_value="ffmpeg"):
            yield

    @pytest.mark.asyncio
    async def test_hls_duplicate_init_map_after_discontinuity_downloads_cleanly(
        self, tmp_path, monkeypatch
    ):
        """첫 세그먼트 뒤에 #EXT-X-DISCONTINUITY와 중복 #EXT-X-MAP이 나와도 HlsFD가 중단 없이 받아야 한다."""
        import yt_dlp

        init0 = tmp_path / "1080p_0_0_0.m4s"
        init1 = tmp_path / "1080p_0_0_1.m4s"
        seg0 = tmp_path / "1080p_0_0_000000.m4v"
        seg1 = tmp_path / "1080p_0_0_000001.m4v"
        init0.write_bytes(b"INIT_HEADER;")
        init1.write_bytes(b"INIT_HEADER;")
        seg0.write_bytes(b"SEG_ZERO;")
        seg1.write_bytes(b"SEG_ONE;")

        playlist = tmp_path / "vod.m3u8"
        playlist.write_text(
            "#EXTM3U\n"
            "#EXT-X-VERSION:7\n"
            "#EXT-X-TARGETDURATION:4\n"
            "#EXT-X-MEDIA-SEQUENCE:0\n"
            "#EXT-X-PLAYLIST-TYPE:VOD\n"
            f'#EXT-X-MAP:URI="{init0.as_uri()}"\n'
            "#EXTINF:3.0,\n"
            f"{seg0.as_uri()}\n"
            "#EXT-X-DISCONTINUITY\n"
            f'#EXT-X-MAP:URI="{init1.as_uri()}"\n'
            "#EXTINF:4.0,\n"
            f"{seg1.as_uri()}\n"
            "#EXT-X-ENDLIST\n",
            encoding="utf-8",
        )

        output_dir = tmp_path / "out"
        output_dir.mkdir()
        engine = VodEngine()
        task = VodDownloadTask(
            url="https://chzzk.naver.com/video/15865579",
            output_dir=str(output_dir),
        )
        engine._tasks[task.task_id] = task

        info_template = {
            "id": "15865579",
            "title": "날개가 달렸다.",
            "uploader": "백나모",
            "extractor": "chzzk:video",
            "extractor_key": "CHZZKVideo",
            "ext": "mp4",
            "protocol": "m3u8_native",
            "url": playlist.as_uri(),
            "webpage_url": task.url,
        }

        def extract_info(ydl, url, download=True):
            info = info_template.copy()
            return ydl.process_ie_result(info, download=True) if download else info

        build_options = engine._build_ytdlp_options

        def local_options(*args, **kwargs):
            return {
                **build_options(*args, **kwargs),
                "enable_file_urls": True,
                # 테스트 환경에 ffmpeg 바이너리가 없어도 HlsFD 결합 동작을 검증할 수 있도록 후처리를 끈다.
                "fixup": "never",
            }

        monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)
        monkeypatch.setattr(engine, "_build_ytdlp_options", local_options)

        await engine._download_external(task.task_id, task)

        assert task.state == VodDownloadState.COMPLETED
        assert task.output_path is not None
        assert Path(task.output_path).read_bytes() == b"INIT_HEADER;SEG_ZERO;SEG_ONE;"

    def test_hls_late_only_init_map_returns_false_from_can_download(self):
        """초기 #EXT-X-MAP 없이 미디어 세그먼트 뒤에만 #EXT-X-MAP이 나오면 FFmpegFD로 위임해야 한다."""
        import yt_dlp.downloader.hls as ytdlp_hls

        late_only_manifest = (
            "#EXTM3U\n"
            "#EXT-X-VERSION:7\n"
            "#EXTINF:3.0,\n"
            "seg0.m4v\n"
            '#EXT-X-MAP:URI="late_init.m4s"\n'
            "#EXTINF:3.0,\n"
            "seg1.m4v\n"
            "#EXT-X-ENDLIST\n"
        )
        assert ytdlp_hls.HlsFD.can_download(late_only_manifest, {"is_live": False}) is False


class TestChzzkCookiesAndQualityOptions:
    """치지직 VOD 쿠키 스트림 전달 및 화질 프리셋 매핑 테스트."""

    @pytest.fixture(autouse=True)
    def mock_ffmpeg_location(self):
        with patch("app.core.config.Settings.resolve_ffmpeg_path", return_value="ffmpeg"):
            yield

    def test_chzzk_url_uses_cookie_stream_without_cookie_header(self, tmp_path):
        """Cookie 헤더 대신 cookiefile 스트림을 사용해 보안 경고 없이 .naver.com 쿠키를 적재한다."""
        import yt_dlp
        from app.engine.auth import AuthManager

        auth = AuthManager(nid_aut="aut_val", nid_ses="ses_val")
        engine = VodEngine(auth=auth)
        for url in (
            "https://chzzk.naver.com/video/15865579",
            "https://apis.naver.com/neonplayer/vodplay/v1/playback/abc?key=123",
        ):
            task = VodDownloadTask(url=url, output_dir=str(tmp_path))
            opts = engine._build_ytdlp_options(task)

            assert "Cookie" not in opts.get("http_headers", {})
            assert "User-Agent" in opts.get("http_headers", {})
            assert opts.get("cookiefile") is not None

            with yt_dlp.YoutubeDL(opts) as ydl:
                for target in (
                    "https://api.chzzk.naver.com/service/v3/videos/15865579",
                    "https://apis.naver.com/neonplayer/vodplay/v1/playback/abc",
                ):
                    cookie_header = ydl.cookiejar.get_cookie_header(target)
                    assert "NID_AUT=aut_val" in cookie_header
                    assert "NID_SES=ses_val" in cookie_header

    def test_quality_presets_map_to_ytdlp_selectors(self, tmp_path):
        """프론트엔드 화질 프리셋(1080p/720p/480p)이 유효한 yt-dlp 포맷 셀렉터로 변환되어야 한다."""
        engine = VodEngine()
        for preset, height in (("1080p", "1080"), ("720p", "720"), ("480p", "480")):
            task = VodDownloadTask(
                url="https://chzzk.naver.com/video/15865579",
                quality=preset,
                output_dir=str(tmp_path),
            )
            opts = engine._build_ytdlp_options(task)
            assert f"height<={height}" in opts["format"]

        custom_task = VodDownloadTask(
            url="https://chzzk.naver.com/video/15865579",
            quality="1080p_0",
            output_dir=str(tmp_path),
        )
        assert engine._build_ytdlp_options(custom_task)["format"] == "1080p_0"

    @pytest.mark.asyncio
    async def test_chzzk_adult_vod_fails_immediately_with_korean_reason_and_notifies(
        self, tmp_path, monkeypatch
    ):
        """성인 인증이 필요한 치지직 VOD는 불필요한 3회 재시도 없이 한국어 안내와 함께 실패해야 한다."""
        import yt_dlp

        notifier = MagicMock()
        engine = VodEngine(notifier=notifier)
        task = VodDownloadTask(
            url="https://chzzk.naver.com/video/99999999",
            output_dir=str(tmp_path),
        )
        engine._tasks[task.task_id] = task
        sleep = AsyncMock()
        monkeypatch.setattr("app.engine.vod.asyncio.sleep", sleep)

        def fail_adult(ydl, url, download=True):
            raise yt_dlp.utils.DownloadError(
                "\x1b[0;31mERROR:\x1b[0m [chzzk:video] 99999999: Adult video is only available to logged-in users"
            )

        monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", fail_adult)

        await engine._run_download(task.task_id)

        assert task.state == VodDownloadState.ERROR
        assert task.error_message is not None
        assert "성인 인증" in task.error_message
        assert "\x1b[" not in task.error_message
        sleep.assert_not_awaited()
        notifier.notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_clip_download_restores_original_url_after_failure(self, tmp_path, monkeypatch):
        """클립 다운로드가 도중에 실패해도 task.url이 임시 재생 URL이 아닌 원래 클립 URL로 유지되어야 한다."""
        clip_url = "https://chzzk.naver.com/clips/testclip123"
        engine = VodEngine()
        task = VodDownloadTask(url=clip_url, output_dir=str(tmp_path))
        engine._tasks[task.task_id] = task

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "content": {
                "contentTitle": "테스트 클립",
                "ownerChannel": {"channelName": "스트리머"},
                "videoId": "hash123",
                "inKey": "key456",
            }
        }

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.get.return_value = mock_resp
        monkeypatch.setattr("app.engine.vod.httpx.AsyncClient", lambda *a, **kw: mock_client)
        monkeypatch.setattr(engine, "_download_external", AsyncMock(side_effect=RuntimeError("boom")))

        with pytest.raises(RuntimeError, match="boom"):
            await engine._download_clip(task.task_id, task)

        assert task.url == clip_url
