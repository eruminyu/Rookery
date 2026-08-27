# Changelog

모든 주목할 만한 변경 사항을 이 파일에서 관리합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.0.0/)를 따르며,
버전 관리는 [Semantic Versioning](https://semver.org/lang/ko/)을 준수합니다.

---

## [Unreleased]

---

## [2.0.1] - 2026-08-27

### Fixed
- **알림 팝오버가 대시보드 콘텐츠에 가려지던 문제**
  - 사이드바의 `backdrop-blur`가 스택 컨텍스트를 만들어, 헤더의 `z-50`이 바깥 본문과
    겨루지 못했다. 사이드바 자체를 본문 위 층(`z-30`)으로 올린다
  - 본문 래퍼 `.page-content`의 `z-10`을 제거했다. 이것이 본문을 스택 컨텍스트로 만들어
    설정 화면의 폴더 선택창과 업데이트 안내 모달까지 함께 가둬 두고 있었다
  - `UpdateModal`만 `z-50`이라 다른 모달(`z-9998`)과 층이 어긋나 있었다
  - 층 순서와 그 이유를 `index.css`에 주석으로 남겼다
- **토스트가 뜰 때마다 화면이 데이터를 다시 불러오던 문제**
  - `useToast()`가 매 렌더마다 새 객체를 반환해, 이 값을 의존성에 넣은 설정·채팅 로그
    화면이 토스트 하나마다 데이터를 통째로 다시 불렀다. 조회 실패로 error 토스트를 띄우면
    실패 → 토스트 → 재조회로 요청이 무한 반복됐다
  - 동작(`ToastActions`)과 내역(`ToastHistoryValue`)을 다른 컨텍스트로 분리했다.
    `useToast()`의 반환값은 이제 마운트 이후 바뀌지 않는다
- **uvicorn의 INFO 로그가 ERROR로 기록되던 문제**
  - stderr로 오는 줄을 전부 `logger.error()`로 찍고 있었다. uvicorn은 INFO를 stderr로
    내보내므로 "Application startup complete."까지 ERROR로 둔갑해, 로그가 온통 ERROR라
    진짜 에러를 골라낼 수 없었다
  - uvicorn 로그를 애플리케이션 핸들러로 직접 라우팅한다. 접근 로그는 프론트 폴링 때문에
    하루 수만 줄이 되므로 종전처럼 콘솔에만 남긴다
  - stderr 줄은 `WARNING:` 같은 접두어로 레벨을 판별한다 (yt-dlp가 이 형식을 쓴다)
- **커맨드 팔레트에 System Logs가 빠져 있던 문제**
  - 사이드바와 팔레트가 화면 목록을 각자 복사해 갖고 있어 어긋나 있었다. 이름과 아이콘도
    서로 달랐다. 목록을 한곳으로 합쳤다

### Changed
- **채팅 로그 조회 성능** — 파일마다 인덱스(메시지 수 + 1000개마다의 바이트 위치)를 DB에
  캐시해, 목록과 페이지 조회가 파일 전체를 다시 읽지 않는다. 104MB 아카이브 기준
  목록 재방문 251ms → 5ms, 페이지 조회 233ms → 0.5ms. 파일이 커지면 늘어난 부분만
  이어서 세므로 녹화 중에도 전체를 다시 읽지 않는다
- 채팅 로그 파일 I/O를 워커 스레드로 옮겼다. 조회하는 동안 SSE 상태 스트림과 다른 API가
  멈추지 않는다
- 네이티브 `alert()` 두 곳을 앱 토스트로 교체했다

### Added
- **DB 스키마 v2** — `chat_file_index` 테이블. 채팅 로그의 메시지 수와 바이트 오프셋을
  담는 파생 데이터이며, 지워져도 다음 조회에서 다시 만들어진다

---

## [2.0.0] - 2026-08-26

### Added
- **즉시 스캔 버튼**: Dashboard에 「즉시 스캔」 버튼 추가 (파란색, RefreshCw 아이콘)
  - `POST /api/platforms/scan-now` 신규 엔드포인트
  - 폴링 주기 무시하고 전체 또는 특정 채널 즉시 상태 확인
- **X Spaces master URL 파일 저장** (녹화 실패 대비 백업)
  - Space 감지 시 master URL을 `.txt` 파일로 저장 (`{download_dir}/x_spaces_urls/`)
  - 파일에 yt-dlp 다운로드 명령어 포함 — 자동 녹화 실패 시 수동 다운로드 가능
  - `ChannelTask.master_url_file` 필드 추가 (persistence 저장/복원 포함)
- **X Spaces Discord 알림 개선**
  - `auto_record=ON`: "🔴 자동 녹화 시작됨 (실시간 저장 중)"
  - `auto_record=OFF`: "⏸️ 자동 녹화 OFF — 아래 URL로 수동 다운로드 가능"
  - Discord `/download-space` 커맨드에 Space URL (`https://x.com/i/spaces/...`) 직접 입력 지원
  - `_get_spaces_embed()`: `master_url` 우선 표시 (없으면 dynamic m3u8 URL 폴백)
- **`download_space(space_url)` 서비스 메서드**: 채널 등록 없이 Space URL로 직접 다운로드
- **`auth.py` `get_streamlink_options()`**: Streamlink 쿠키 주입 헬퍼 메서드

### Changed
- **프로젝트명 변경: Signal-Recorder → Rookery**
  - `Signal`이 메신저 앱과 충돌해 검색에서 묻히고, `Recorder`가 기능의 일부만 설명했다.
    표기도 4종(`Signal-Recorder` / `signal-recorder` / `signal_recorder` / `Signal Recorder`)이 혼재했다
  - 코드 식별자(`channel`, `recording` 등 도메인 용어)와 저장 폴더 `recordings/` 는 그대로 둔다
  - **DB 파일 `signal_recorder.db` → `rookery.db`**: 기동 시 자동 이관한다.
    `-wal` / `-shm` 사이드카도 함께 옮기고, 이관에 실패하면 빈 DB를 만드는 대신
    기존 파일을 그대로 사용한다
  - **systemd 유닛 `signal-recorder` → `rookery`**: 등록 전에 구버전 유닛을 중지·제거한다.
    남아 있으면 같은 포트를 물고 있어 새 유닛이 뜨지 못한다
  - **설치 경로 `~/signal-recorder` → `~/rookery`**: 기존 설치가 있으면 그대로 이어받는다
  - **관리 명령 `signal-recorder` → `rookery`**
  - 브라우저에 저장된 페이지 타이틀이 옛 기본값과 정확히 일치하면 새 기본값으로 승격한다.
    사용자가 직접 지정한 값은 건드리지 않는다
  - **아직 남은 것**: GitHub 리포지토리 이름. 코드의 리포 슬러그는 실제 리포를 바꾸기 전까지
    그대로 둔다 — 먼저 바꾸면 업데이트 체커가 404를 받고 설치 원라이너가 죽는다
- **알림 설정 화면을 웹훅 우선으로 재배치**
  - Bot 카드가 먼저 오고 Webhook이 "폴백"으로 뒤에 있어, 알림만 필요한 사용자도
    개발자 포털에서 앱을 만들어야 하는 것처럼 보였다
  - Webhook을 기본 경로로 올리고, Bot은 접힌 고급 섹션으로 내렸다
    (이미 설정한 사용자에게는 펼친 채로 보여준다)
- **설치·실행·업데이트 스크립트를 하나로 통합** (`scripts/manage.sh`, `scripts/manage.bat`)
  - 제거: `install.sh`, `install-docker.sh`, `update-docker.sh`, `setup_service.sh`,
    `signal-recorder.service`, `install.bat`, `start.bat`, `start-dev.bat`
  - 색상 변수·출력 헬퍼·OS 감지·저장소 클론·완료 메시지가 스크립트마다 2~3벌씩
    중복되어 있었고, systemd 유닛이 일반 유닛과 템플릿 유닛 두 갈래로 갈라져 있었다
  - 원라이너 하나가 설치와 업데이트를 겸한다. 미설치면 설치, 설치되어 있으면 갱신 후 재시작
  - 설치 후 `signal-recorder` 명령이 등록되어 `status` / `update` / `start` / `stop` /
    `logs` / `service` / `uninstall` 을 한 단어로 실행한다
  - 네이티브 설치 전용이다. Docker는 `docker compose up --build -d` 를 직접 사용한다
  - **기존 사용자 영향**: 원라이너 URL이 `scripts/install.sh` → `scripts/manage.sh` 로 바뀌었다.
    네이티브 설치에는 그동안 업데이트 스크립트가 없었으나 이제 `signal-recorder update` 로 갱신한다.
- **`.gitattributes` 추가**: `*.sh` 는 LF, `*.bat` 은 CRLF로 고정.
  셸 스크립트가 CRLF로 체크아웃되면 셔뱅이 `bash` 로 읽혀 원라이너 설치가 실패한다.
- **Discord 봇 명령을 슬래시 커맨드 전용으로 전환** (기존 `!` 프리픽스 명령 제거)
  - 프리픽스와 슬래시로 중복 구현되어 있던 핸들러 10개 제거 — 공통 로직은 이미 헬퍼로 분리되어 있어 기능 손실 없음
  - `message_content` privileged intent 요구 제거 → Discord 개발자 포털에서 별도 활성화 불필요
  - 빌트인 `!help` 비활성화 (`help_command=None`)
  - **기존 사용자 영향**: `!status`, `!start` 등 프리픽스 명령이 더 이상 동작하지 않습니다. `/status`, `/start`를 사용하세요.


### Fixed
- **X Spaces 종료 감지 버그**: `AudioSpaceById` `state` 미검사로 종료된 Space가 `is_live=True` 유지되던 문제
  - UserTweets 타임라인에 종료 Space가 남아 있어 space_id가 계속 발견되던 근본 원인
  - `state != "Running"` 이면 즉시 `_offline_status()` 반환
  - `.part` 파일 잔류 문제 해결 (5분 이내 폴링에서 종료 감지 → yt-dlp 프로세스 종료)
- **X Spaces 다음 Space master URL 미캡처**: Space 종료 감지 시 `master_url` 등 X Spaces 전용 필드 전체 초기화
  - 미초기화로 인해 `if new_master and not task.master_url:` 조건이 항상 False
- **`toggle_auto_record()` async 누락**: Conductor → RecorderService → API 라우터 전 계층 `await` 누락 수정

### Security
- **Discord 봇 명령 권한 검사 추가**: 기존에는 호출자·채널 검증이 전혀 없어, 봇이 초대된 서버의 누구나 남의 녹화를 시작·중단할 수 있었음
  - `DISCORD_COMMAND_USER_IDS` / `DISCORD_COMMAND_CHANNEL_ID` 설정 추가 (설정 → 알림 탭에서도 변경 가능)
  - 판정은 `_is_authorized()` 단일 지점에서 수행하고, `CommandTree.interaction_check`로 모든 슬래시 커맨드에 일괄 적용
  - 미설정 시 `DISCORD_NOTIFICATION_CHANNEL_ID`를 채널 조건으로 사용하며, 그마저 없으면 모든 명령을 거부 (fail-closed)
  - **기존 사용자 영향**: 알림 채널 밖에서 명령을 사용하던 경우 거부됩니다.


---

## [1.1.0] - 2026-03-24

### Added
- **멀티 플랫폼 감시**: TwitCasting, Twitter Spaces 채널 자동 감시 및 녹화 지원
  - `Platform` 열거형 기반 플랫폼 추상화 (`base.py`)
  - `ChannelTask`에 `platform` 필드 추가, 복합 키(`platform:channel_id`) 방식으로 채널 관리
  - TwitCasting 엔진: TwitCasting API v2 + Streamlink 스트림 추출 (`twitcasting.py`)
  - Twitter Spaces 엔진: 비공식 GraphQL API + m3u8 URL 캡처 (`twitter_spaces.py`)
  - Dashboard에 플랫폼 드롭다운 및 플랫폼 배지(치지직/TwitCasting/Twitter Spaces) 표시
  - 인증 미설정 플랫폼 채널 추가 시 자물쇠 아이콘 + 잠금 처리

- **Twitter Spaces m3u8 캡처 및 수동 캡처 모드**
  - 비공식 GraphQL `UserByScreenName` → `UserTweets` 타임라인 폴링으로 Space 감지
  - Space 라이브 시 `dynamic_playlist.m3u8` URL 자동 추출 및 `channels.json` 영속 저장
  - 429 Rate Limit 대응: 자동 감시 루프 비활성화 → Discord `/capture-space` 수동 캡처 방식 전환
  - Discord 슬래시/프리픽스 커맨드: `/capture-space`, `!capture-space`

- **아카이브 다운로드 기능**
  - TwitCasting 채널 과거 방송 목록 조회 및 다운로드 (`GET /api/archive/twitcasting/{channel_id}`)
  - Twitter Spaces m3u8 URL 직접 입력 다운로드
  - 캡처된 m3u8 URL 목록 조회/다운로드/삭제 API (`/api/archive/spaces/*`)
  - Archive 페이지 신규 추가 (사이드바 메뉴 포함)

- **Twitter 쿠키 만료 감지 + Discord 알림**
  - `verify_cookie()`: `GET /1.1/account/verify_credentials.json` 호출로 쿠키 유효성 24시간 주기 검증
  - 만료 감지 시 Discord 알림 자동 발송 (중복 발송 방지)
  - Discord 커맨드: `/spaces`, `!spaces`, `/download-space`, `!download-space`
  - `GET /api/settings/cookie-status`, `POST /api/settings/cookie-status/check` API 추가

- **Settings 탭 구조 개편**
  - 「일반」「다운로드」「인증」「알림」「외관」「정보」6탭 구조로 전면 재편
  - 인증 탭: Chzzk / TwitCasting / Twitter Spaces 3개 섹션 통합 관리

### Fixed
- 원격 접속 시 API 호출 실패: `API_BASE_URL` 절대경로 → 상대경로(`/api`)로 변경
- Docker `appuser` uid 불일치로 `.env`/`recordings/` 쓰기 실패 → root 실행으로 전환
- Docker 초기 설정 시 컨테이너 내부 경로(`/app/recordings`) 기본값 안내 추가

---

## [1.0.0] - 2026-03-12

### Added
- **채널 모니터링**: 치지직 채널 자동 감시 및 방송 시작 시 녹화 자동 시작
- **라이브 녹화**: streamlink + FFmpeg Hybrid Pipe 엔진을 통한 고품질 녹화
  - 지원 포맷: `ts`, `mp4`, `mkv`
  - 지원 품질: `best`, `1080p`, `720p`, `480p`
- **VOD 다운로드**: 치지직 VOD 및 외부 URL(YouTube 등) 다운로드 지원
  - 동시 다운로드 최대 설정 가능
  - 다운로드 속도 제한 설정 가능
- **채팅 아카이빙**: 녹화 시 실시간 채팅 자동 저장
- **채널 영속성**: `channels.json`으로 채널 목록 자동 저장/복원
- **설정 UI**: Web 기반 설정 화면에서 모든 옵션 변경 가능
- **Discord 봇 연동**: 방송 시작/종료, 녹화 알림 Discord 채널 전송
- **통계 대시보드**: 녹화 현황 및 디스크 사용량 통계 제공

### 배포
- **Docker 지원**: Multi-stage 빌드 Docker 이미지 및 `docker-compose.yml` 제공
- **Windows 배포**: PyInstaller 기반 단독 실행 `.exe` (FFmpeg/streamlink 내장)
  - 시스템 트레이 아이콘 (종료, 브라우저 열기)
  - 서버 시작 시 기본 브라우저 자동 오픈
- **Linux Native 배포**: 설치 스크립트 및 systemd 서비스 템플릿 제공
- **통합 서버**: FastAPI가 React 빌드 파일을 직접 서빙 (포트 하나로 통합)

---

[Unreleased]: https://github.com/eruminyu/Rookery/compare/v2.0.1...HEAD
[2.0.1]: https://github.com/eruminyu/Rookery/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/eruminyu/Rookery/compare/v1.1.7...v2.0.0
[1.1.0]: https://github.com/eruminyu/Rookery/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/eruminyu/Rookery/releases/tag/v1.0.0
