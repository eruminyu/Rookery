# Done: Signal-Recorder → Rookery 리네이밍

## 개요

프로젝트 명칭을 `Signal-Recorder`에서 `Rookery`로 변경했다.

기존 이름의 문제:
- `Signal`이 메신저 앱과 충돌해 검색에서 묻힌다
- `Recorder`가 기능의 일부만 설명한다 (실제로는 VOD 다운로드, 채팅 아카이브, 통계, 알림 포함)
- `Signal-Recorder` / `signal-recorder` / `signal_recorder` / `Signal Recorder` 4종 표기가 혼재했다

`Rookery`는 떼까마귀의 집단 둥지다. 여러 채널을 한 화면에서 감시하는 대시보드 구조와
의미가 맞고, 한 단어라 표기 혼재가 구조적으로 사라진다.

## 표기 규칙

| 용도 | 표기 |
|------|------|
| 정식 명칭 | `Rookery` |
| 슬러그 / 패키지 / 도커 / 명령 | `rookery` |
| DB 파일 | `rookery.db` |
| systemd 유닛 | `rookery.service` |
| Windows 릴리즈 | `Rookery.exe` |

## 적용 범위 원칙

코드 식별자(`channel`, `recording`, `vod_queue` 등 도메인 용어)는 **변경하지 않았다.**
이미 정확한 용어이고, 컨셉에 맞춰 바꾸면 가독성만 나빠지고 diff가 불필요하게 커진다.
컨셉은 사람이 읽는 표면(UI 카피, 로고, 문서, 봇 표시명)에만 반영한다.

저장 폴더 `recordings/`도 그대로 뒀다. 바꾸면 기존 사용자 경로가 깨진다.

---

## 호환성이 깨지는 항목과 처리

### 1. DB 파일명 — 런타임 이관

`backend/data/`는 `.gitignore` 대상이라 DB는 사용자 로컬에만 존재한다.
상수만 바꾸면 빈 DB가 새로 생겨 채널 목록·녹화 이력·태그가 사라진 것처럼 보인다.

`backend/app/store/db.py`의 `_resolve_db_path()`가 기동 시 처리한다.

- `rookery.db`가 없고 `signal_recorder.db`가 있으면 새 이름으로 옮긴다
- `-wal`, `-shm` 사이드카도 함께 옮긴다 — 본체 파일명에 묶여 있어 따로 두면
  비정상 종료 직전의 트랜잭션을 잃는다
- 이관에 실패하면 **옛 파일을 그대로 쓴다.** 빈 DB를 만들어 데이터가 사라진 것처럼
  보이는 상황이 최악이다

`backend/tests/test_store.py`의 `TestDbFilenameMigration`이 5개 경우를 검증한다.

### 2. 브라우저에 저장된 페이지 타이틀 — 승격

페이지 타이틀은 브라우저별로 커스터마이징되어 `localStorage`에 남는다.
기본값 상수만 바꾸면 기존 사용자 화면에는 계속 옛 이름이 보인다.

`frontend/src/context/ThemeContext.tsx`의 `readStoredTitle()`이 처리한다.
저장값이 옛 기본값(`Signal Recorder` / `Signal-Recorder`)과 **정확히 일치할 때만**
새 기본값으로 승격하고, 사용자가 직접 지정한 값은 그대로 둔다.

### 3. systemd 유닛명 — 구버전 제거 후 등록

유닛명이 `signal-recorder.service` → `rookery.service`로 바뀌었다.
옛 유닛이 남아 있으면 같은 포트를 물고 있어 새 유닛이 뜨지 못한다.

`scripts/manage.sh`의 `remove_legacy_service()`가 등록 전에 걷어낸다.

### 4. 설치 경로 — 레거시 경로 인식

기본 설치 경로가 `~/signal-recorder` → `~/rookery`로 바뀌었다.
`resolve_install_dir()`의 레거시 목록에 `~/signal-recorder`를 남겨,
기존 설치를 그대로 이어받는다.

---

## GitHub 리포지토리 이름 — 완료

리포 슬러그는 **가장 마지막에** 바꿨다. 코드가 먼저 새 이름을 가리키면 실제 리포를
바꾸기 전까지 업데이트 체커가 404를 받고 설치 원라이너도 죽는다. 실사용 중인
프로그램이라 그 공백을 만들 수 없었다.

`eruminyu/Signal-Recorder` → `eruminyu/Rookery` 로 바꾼 위치:

- `backend/app/engine/updater.py` — `GITHUB_REPO`
- `scripts/manage.sh` — `REPO_SLUG` (`REPO_URL`과 `RAW_URL`이 여기서 파생된다)
- `README.md`, `docs/linux-guide.md`, `docs/handoff-2026-08-25.md` — clone / 원라이너 URL과 `cd` 대상

GitHub이 옛 이름으로 오는 요청을 리다이렉트해 주므로 구버전 클라이언트의 업데이트
확인도 당장은 동작한다. 다만 영구 보장은 아니다.

**아직 남은 것**: 다음 릴리즈의 asset 파일명을 `Rookery.exe`로 맞추기.
PyInstaller 스펙(`*.spec`)은 gitignore 대상이라 저장소에 없으므로
빌드 머신에서 직접 고쳐야 한다.

---


## 손대지 않은 문서

`docs/done-*.md`와 완료된 `plan-*.md`, `checklist.md`, `CHANGELOG.md`의 과거 항목은
당시 기록이므로 옛 이름 그대로 뒀다. 원문을 유지하는 편이 히스토리로서 정확하다.
