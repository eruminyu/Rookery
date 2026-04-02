# Signal-Recorder 통합 기능 명세서

## 1. 개요
**Signal-Recorder**는 네이버 치지직(Chzzk) 플랫폼을 위한 올인원 녹화 및 다운로드 솔루션입니다.
라이브 스트리밍 자동 녹화, VOD/클립 다운로드, 실시간 채팅 아카이빙, 그리고 통계 대시보드를 제공하며, 웹 기반 UI를 통해 모든 기능을 제어할 수 있습니다.

## 2. 기술 스택

### Backend
- **Language**: Python 3.12+
- **Framework**: FastAPI (ASGI)
- **Core Libraries**:
  - `yt-dlp`: 라이브 스트림 추출 및 VOD 다운로드
  - `ffmpeg-python`: 비디오 인코딩 및 처리
  - `chzzkpy`: 치지직 API 연동 (채팅, 채널 정보)
- **Database**: JSON 파일 기반 로컬 스토리지 (NoSQL-like)

### Frontend
- **Language**: TypeScript
- **Framework**: React (Vite)
- **UI Library**: TailwindCSS, Shadcn/UI, Lucide React
- **State Management**: React Hooks, Context API

---

## 3. 시스템 아키텍처

### 3.1. Engine Layer
- **Conductor**: 라이브 스트리밍 감시 및 녹화 제어의 핵심 엔진. `Streamlink` 프로세스를 관리하고 `FFmpeg` 파이프라인을 통해 영상을 저장합니다.
- **VodEngine**: VOD 다운로드 작업 관리자. 대기열(Queue) 시스템을 갖추고 있으며, 치지직 VOD는 `Streamlink`, 외부 VOD는 `yt-dlp`를 사용합니다.
- **ChatArchiver**: WebSocket을 통해 실시간 채팅을 수집하고 `.jsonl` 포맷으로 저장합니다.

### 3.2. Service Layer
- **RecorderService**: API와 Engine 사이의 중개자. 비즈니스 로직을 캡슐화하고 싱글톤으로 동작합니다.
- **DiscordBotService**: 녹화 시작/종료, 다운로드 완료 등 주요 이벤트를 Discord로 알림 전송합니다.

### 3.3. Interface Layer
- **REST API**: 프론트엔드와 통신하는 API 엔드포인트 (`/api/stream`, `/api/vod`, `/api/settings`, `/api/chat`, `/api/stats`).
- **Web UI**: SPA(Single Page Application)로 구현된 사용자 인터페이스.

---

## 4. 상세 기능 명세

### 4.1. 라이브 녹화 (Live Recording)
- **자동 녹화**: 등록된 채널의 방송 시작을 감지하여 자동으로 녹화를 시작합니다.
- **수동 녹화**: 사용자가 원할 때 즉시 녹화를 시작하거나 중단할 수 있습니다.
- **안정성**:
  - `Fragmented MP4` 옵션을 사용하여 녹화 중 비정상 종료(정전 등) 시에도 파일 손상을 방지합니다.
  - 스트림 끊김 시 자동 재연결을 시도합니다.
- **채널 관리**: 채널별 자동 녹화 ON/OFF 설정, 실시간 방송 상태(썸네일, 시청자 수, 제목) 모니터링.

### 4.2. VOD 다운로드 (VOD Downloader)
- **치지직 지원**: 다시보기(VOD) 및 클립 다운로드를 지원합니다. (Streamlink + FFmpeg 파이프라인 사용으로 안정성 확보)
- **외부 사이트 지원**: YouTube 등 `yt-dlp`가 지원하는 외부 사이트 URL 다운로드 가능.
- **대기열 관리**:
  - 다운로드 작업의 우선순위를 드래그 앤 드롭으로 변경 가능.
  - 일시정지, 재개, 취소, 재시도 기능 제공.
- **경로 분할**: 치지직 VOD와 외부 VOD를 서로 다른 폴더에 저장하도록 설정 가능.

### 4.3. 채팅 아카이빙 (Chat Archiving)
- **실시간 수집**: 라이브 녹화 시 해당 방송의 채팅을 실시간으로 수집합니다.
- **저장 포맷**: `.jsonl` (JSON Lines) 형식으로 저장되어 타임스탬프, 닉네임, 메시지, 배지 정보 등을 포함합니다.
- **웹 뷰어**:
  - 날짜별, 채널별 채팅 로그 파일 탐색.
  - 키워드 및 닉네임 검색 기능.
  - 웹에서 바로 조회하거나 원본 파일 다운로드 가능.

### 4.4. 통계 대시보드 (Statistics)
- **종합 지표**: 총 녹화 시간, 총 녹화 용량, VOD 다운로드 수, 저장소 사용량(Disk Usage) 시각화.
- **채널별 통계**: 채널별 녹화 횟수, 총 시간, 용량, 최근 30일 라이브 감지 횟수 제공.
- **세션 이력**: 최근 완료된 녹화 세션 목록 표시.

### 4.5. 설정 및 알림 (Settings & Notification)
- **Discord 알림**: Webhook이 아닌 봇 토큰 방식을 사용하여 녹화 시작/종료/에러, VOD 완료 시 알림을 전송합니다.
- **경로 설정**: 녹화 파일 저장 경로, VOD 분할 저장 경로 등을 웹 UI에서 브라우징하여 설정 가능.
- **인증 관리**: `NID_AUT`, `NID_SES` 쿠키를 설정하여 성인 인증 방송 녹화 지원.

---

## 5. 데이터 구조

- **`channels.json`**: 감시 대상 채널 목록 및 설정.
- **`vod_history.json`**: VOD 다운로드 이력 및 상태.
- **`live_history.json`**: 완료된 라이브 녹화 세션 이력.
- **`settings.json`** (또는 `.env`): 애플리케이션 전역 설정.
- **`recordings/`**: 녹화된 영상 및 채팅 로그 저장소.