"""
test_api_surface.py
공개 API 표면을 고정한다.

이 프로젝트의 1번 규칙은 "API 계약을 바꾸지 않는다"이다. 그런데 라우트는
데코레이터로 등록돼서, 파일을 옮기다 실수로 빠뜨려도 파싱도 import도 성공한다.
실제로 설정 라우터를 도메인별로 나누다 라우트 15개를 통째로 잃은 적이 있고,
그때는 이 목록을 손으로 대조해서야 알았다.

경로가 바뀌면 이 테스트가 먼저 깨진다. 의도한 변경이라면 아래 EXPECTED_ROUTES를
함께 고치면 되고, 그 diff가 곧 "API를 바꿨다"는 기록이 된다.
"""

from app.main import app

#: (HTTP 메서드, 경로). 메서드는 쉼표로 이어 붙이고 HEAD는 뺀다
#: (FastAPI가 GET에 자동으로 붙여주는 것이라 계약이 아니다).
EXPECTED_ROUTES = {
    ("GET", "/"),
    ("POST", "/api/archive/download"),
    ("GET", "/api/archive/spaces/captured"),
    ("DELETE", "/api/archive/spaces/captured/{composite_key:path}"),
    ("POST", "/api/archive/spaces/download-captured"),
    ("GET", "/api/archive/twitcasting/{channel_id}"),
    ("GET", "/api/chat/files"),
    ("GET", "/api/chat/files/{file_id}/download"),
    ("GET", "/api/chat/files/{file_id}/messages"),
    ("GET", "/api/events"),
    ("GET", "/api/platforms/channels"),
    ("POST", "/api/platforms/channels"),
    ("DELETE", "/api/platforms/channels/{platform}/{channel_id:path}"),
    ("PATCH", "/api/platforms/channels/{platform}/{channel_id:path}/auto-record"),
    ("POST", "/api/platforms/scan-now"),
    ("PUT", "/api/platforms/settings/twitcasting"),
    ("GET", "/api/platforms/status"),
    ("DELETE", "/api/platforms/x/cookie"),
    ("POST", "/api/platforms/x/cookie"),
    ("GET", "/api/settings"),
    ("GET", "/api/settings/"),
    ("GET", "/api/settings/auth"),
    ("GET", "/api/settings/browse-dirs"),
    ("PUT", "/api/settings/chat"),
    ("GET", "/api/settings/cookie-status"),
    ("POST", "/api/settings/cookie-status/check"),
    ("PUT", "/api/settings/cookies"),
    ("POST", "/api/settings/cookies/test"),
    ("PUT", "/api/settings/discord"),
    ("GET", "/api/settings/discord/status"),
    ("POST", "/api/settings/discord/test"),
    ("PUT", "/api/settings/download"),
    ("PUT", "/api/settings/general"),
    ("PUT", "/api/settings/vod"),
    ("POST", "/api/setup/complete"),
    ("GET", "/api/setup/status"),
    ("GET", "/api/stats"),
    ("GET", "/api/stats/"),
    ("GET", "/api/stream/channels"),
    ("POST", "/api/stream/channels"),
    ("DELETE", "/api/stream/channels/{channel_id:path}"),
    ("PATCH", "/api/stream/channels/{channel_id:path}/auto-record"),
    ("POST", "/api/stream/monitor/start"),
    ("POST", "/api/stream/monitor/stop"),
    ("POST", "/api/stream/record/stop-all"),
    ("POST", "/api/stream/record/{channel_id:path}/start"),
    ("POST", "/api/stream/record/{channel_id:path}/stop"),
    ("GET", "/api/system/logs"),
    ("GET", "/api/system/logs/{filename:path}"),
    ("GET", "/api/system/update"),
    ("POST", "/api/system/update/check"),
    ("GET", "/api/tags"),
    ("POST", "/api/tags"),
    ("PATCH", "/api/tags/channel/{channel_id:path}"),
    ("DELETE", "/api/tags/{tag_name:path}"),
    ("POST", "/api/vod/clear-completed"),
    ("POST", "/api/vod/download"),
    ("POST", "/api/vod/info"),
    ("POST", "/api/vod/reorder"),
    ("GET", "/api/vod/status"),
    ("GET", "/api/vod/status/{task_id}"),
    ("POST", "/api/vod/{task_id}/cancel"),
    ("POST", "/api/vod/{task_id}/open-location"),
    ("POST", "/api/vod/{task_id}/pause"),
    ("POST", "/api/vod/{task_id}/resume"),
    ("POST", "/api/vod/{task_id}/retry"),
    ("GET", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("GET", "/health"),
    ("GET", "/health/detail"),
    ("GET", "/openapi.json"),
    ("GET", "/redoc"),
    ("GET", "/{full_path:path}"),
}


def _current_routes() -> set[tuple[str, str]]:
    found = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        if not methods:
            # StaticFiles 마운트 등 메서드가 없는 것은 계약 대상이 아니다.
            continue
        listed = ",".join(sorted(m for m in methods if m != "HEAD"))
        found.add((listed, getattr(route, "path", "")))
    return found


def test_public_api_surface_is_unchanged():
    """등록된 라우트가 기대 목록과 정확히 같아야 한다."""
    current = _current_routes()

    removed = sorted(EXPECTED_ROUTES - current)
    added = sorted(current - EXPECTED_ROUTES)

    message = []
    if removed:
        message.append(
            "사라진 라우트 (배포된 구버전 클라이언트가 호출하던 것일 수 있다):\n  "
            + "\n  ".join(f"{m} {p}" for m, p in removed)
        )
    if added:
        message.append(
            "새로 생긴 라우트 (의도한 것이라면 EXPECTED_ROUTES에 추가한다):\n  "
            + "\n  ".join(f"{m} {p}" for m, p in added)
        )

    assert not message, "\n\n".join(message)
