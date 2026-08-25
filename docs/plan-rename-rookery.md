# plan-rename-rookery

## 목적

프로젝트 명칭을 `Signal-Recorder` → `Rookery`로 변경한다.

기존 이름의 문제:
- `Signal`이 메신저 앱과 충돌해 검색에서 묻힌다
- `Recorder`가 기능의 일부만 설명한다 (실제로는 VOD 다운로드, 채팅 아카이브, 통계, 알림 포함)
- `Signal-Recorder` / `signal-recorder` / `signal_recorder` / `Signal Recorder` 4종 표기가 혼재한다

`Rookery`는 떼까마귀의 집단 둥지를 뜻한다. 여러 채널을 한 화면에서 감시하는 대시보드 구조와 의미가 일치하고,
한 단어이므로 표기 혼재가 구조적으로 사라진다.

## 표기 규칙

| 용도 | 표기 |
|------|------|
| 정식 명칭 | `Rookery` |
| 슬러그 / 패키지 / 도커 | `rookery` |
| DB 파일 | `rookery.db` |
| systemd 유닛 | `rookery.service` |
| Windows 릴리즈 | `Rookery.exe` |

모든 컨텍스트에서 `rookery` 한 형태만 사용한다.

## 적용 범위 원칙

코드 식별자(`channel`, `recording`, `vod_queue` 등 도메인 용어)는 **변경하지 않는다.**
이미 정확한 용어이고, 컨셉에 맞춰 바꾸면 가독성만 나빠지고 diff가 불필요하게 커진다.

컨셉은 사람이 읽는 표면(UI 카피, 로고, 문서, 봇 표시명)에만 반영한다.

## 현황

이름 문자열 약 148건 / 60여 파일.

| 패턴 | 건수 |
|------|-----:|
| `Signal-Recorder` | 93 |
| `signal-recorder` | 42 |
| `signal_recorder` | 13 |
| `Signal Recorder` | 9 |
| `SignalRecorder` | 1 |

이 중 호환성이 깨지는 것은 6곳이고, 나머지는 단순 표기 치환이다.

---

## Tier 1 — 호환성이 깨지는 항목

### 1. DB 파일명

**변경 파일**
- `backend/app/store/db.py:30` — `DB_FILENAME = "signal_recorder.db"`

**문제**
`backend/data/`는 `.gitignore` 대상이라 DB는 사용자 로컬에만 존재한다.
상수만 바꾸면 기존 사용자의 채널 목록·녹화 이력·태그가 전부 유실된 것처럼 보인다.

**구현 내용**
- 기동 시 `rookery.db`가 없고 `signal_recorder.db`가 있으면 자동 rename 후 사용
- 둘 다 없으면 `rookery.db` 신규 생성
- rename 성공/실패를 로그로 남긴다

### 2. GitHub 리포지토리 및 업데이트 체커

**변경 파일**
- `backend/app/engine/updater.py:17` — `GITHUB_REPO = "eruminyu/Signal-Recorder"`
- `frontend/src/components/ui/UpdateModal.tsx:30` — 릴리즈 asset 안내 `Signal_Recorder.exe`
- `frontend/src/components/ui/UpdateModal.tsx` — 업데이트 안내 명령 `signal-recorder update`

**문제**
리포 이름을 바꾸면 구버전 클라이언트의 업데이트 확인 경로가 영향을 받는다.
GitHub이 리다이렉트를 제공하지만 `raw.githubusercontent.com`과 릴리즈 asset 파일명까지 그대로
동작하는지는 실제 릴리즈에서 직접 확인해야 한다.

### 3. 설치 스크립트

**변경 파일**
- `scripts/manage.sh` — 원라이너 URL, `APP_NAME`, `SERVICE_NAME`, 기본 설치 경로, 유닛 정의
- `scripts/manage.bat` — 안내 문구
- `scripts/healthcheck.sh` — 설치 경로, systemd 유닛명, DB 파일명

**문제**
이미 배포된 `curl | bash` 원라이너가 죽는다. 설치 후 등록되는 명령 이름
(`~/.local/bin/signal-recorder`), 기본 설치 경로 `~/signal-recorder`, systemd 유닛명이
모두 바뀌므로 기존 리눅스 사용자는 마이그레이션이 필요하다.

**구현 내용**
- 신규 설치 경로 `~/rookery`, 명령 `rookery`, 유닛명 `rookery.service`
- `resolve_install_dir()`의 레거시 경로 목록에 `~/signal-recorder`를 남겨 기존 설치를 이어받는다
- 옛 유닛(`signal-recorder.service`)이 남아 있으면 제거 후 새 유닛을 등록한다
- README와 릴리즈 노트의 설치 명령 동시 갱신

### 4. 브라우저 저장 타이틀

**변경 파일**
- `frontend/src/context/ThemeContext.tsx:24` — `DEFAULT_TITLE = "Signal Recorder"`
- `frontend/src/components/settings/AppearanceTab.tsx:70,86` — placeholder 및 초기화 값

**문제**
페이지 타이틀은 브라우저별로 커스터마이징되어 localStorage에 저장된다.
기본값만 바꾸면 기존 사용자 화면에는 여전히 `Signal Recorder`가 표시된다.

**구현 내용**
- 저장값이 옛 기본값(`Signal Recorder`)과 정확히 일치하면 새 기본값으로 승격
- 사용자가 직접 지정한 값은 그대로 보존

### 5. PyInstaller 스펙

`*.spec`은 `.gitignore` 대상이라 리포에 없다. `Rookery.exe` 산출물명 변경은
빌드 머신의 스펙 파일에서 직접 처리해야 하며, 이 계획의 코드 변경으로는 해결되지 않는다.

---

## Tier 2 — 기능 식별자

| 파일 | 작업 |
|------|------|
| `frontend/package.json` | `"name": "signal-recorder"` → `"rookery"` (+ lock 갱신) |
| `.claude/launch.json` | 구성 `name` 변경 |
| `docker-compose.yml` | 서비스명, `container_name`, 21행 주석의 DB 파일명 |
| `.env.example:1` | 헤더 주석 |
| `backend/app/static/` | 빌드 산출물. 프론트 재빌드로 자동 해결 |

`container_name` 변경은 기존 컨테이너를 재생성하지만, 볼륨이 전부 bind mount라 데이터는 안전하다.

---

## Tier 3 — 표기 치환

- 백엔드 모듈 docstring 헤더 약 30개 (`"""Signal-Recorder: ..."""`)
- `backend/app/version.py` docstring
- `frontend/index.html` — `<title>`, description
- UI 문자열 — `frontend/src/App.tsx:36`, `components/layout/Sidebar.tsx:168`,
  `components/SetupWizard.tsx:314`, `components/settings/AppearanceTab.tsx:70`
- `scripts/generate_icon.py:3,21`
- `README.md`, `docs/` 문서

`docs/done-*.md`는 당시 작업 기록이므로 **변경하지 않는다.** 원문 그대로 두는 편이 히스토리로서 정확하다.

---

## 로고 / 컬러

- 포인트 컬러 `#13d9a3`(민트) **유지.** 까마귀 검정과 대비가 좋고 다크 UI 전반에 이미 적용되어 있다
- 마크는 파비콘 16px에서 뭉개지지 않도록 실루엣 하나로 처리
  - A안: 까마귀 옆모습 실루엣, 눈에만 민트 포인트 (REC 인디케이터와 호응)
  - B안: 각진 부리 형태의 추상 마크
- `scripts/generate_icon.py`가 Pillow로 아이콘을 생성하므로 마크 확정 후 해당 스크립트만 교체

## UI 카피

- 빈 상태: "둥지가 아직 비어 있습니다"
- Discord 봇 표시명: `Rookery`
- 저장 폴더명 `recordings/` → `roost/`는 기존 경로가 깨지므로 **적용하지 않는다**

---

## 구현 순서

1. Tier 3 표기 치환 + UI 문자열 — 되돌리기 쉬우므로 여기서 어감을 최종 확인한다
2. Tier 2 기능 식별자
3. Tier 1 중 코드 내에서 완결되는 것 — DB 폴백, `DEFAULT_TITLE` 승격
4. 로고·파비콘 교체
5. GitHub 리포 rename + 새 릴리즈(`Rookery.exe`) + README 설치 명령 갱신

5번을 마지막에 두는 것이 중요하다. 코드가 준비되기 전에 리포 이름부터 바꾸면
그 사이 업데이트 체커가 참조할 대상이 사라진다.

## 예상 영향 범위

- 기존 사용자는 DB 자동 rename으로 데이터가 보존되나, 실패 시 로그 확인이 필요하다
- 리눅스 native 설치 사용자는 설치 경로와 systemd 유닛명 수동 마이그레이션이 필요하다
- 배포된 `curl | bash` 설치 명령이 갱신 전까지 동작하지 않을 수 있다
- 기능 변경은 없다

## 선행 조건

`backend/app/services/discord_bot.py`와 알림 설정 탭은 별도 워크트리에서
Discord 명령 권한 체크 작업이 진행 중이다. 해당 작업 병합 후 Tier 3 치환을 시작한다.
