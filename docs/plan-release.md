# Phase 9: 배포 및 릴리즈 전략

## 개요

기능 개발이 완료된 **Signal-Recorder**를 최종 사용자가 쉽게 설치하고 사용할 수 있도록 패키징한다.
프론트엔드(React)와 백엔드(FastAPI)를 별도로 실행하는 개발 환경과 달리, 배포 시에는 **백엔드가 프론트엔드 정적 파일을 서빙**하는 통합 구조를 채택한다.

## 배포 대상 플랫폼

1.  **Docker (권장)**: OS에 구애받지 않는 가장 안정적인 배포 방식 (Linux, NAS, Windows w/ Docker)
2.  **Windows Desktop**: 별도 설치 없이 실행 가능한 `.exe` (PyInstaller 사용)
3.  **Linux (Native)**: Ubuntu 및 기타 배포판을 위한 설치 스크립트 및 Systemd 서비스 등록

---

## 1. 통합 빌드 전략 (공통)

배포의 복잡도를 낮추기 위해 프론트엔드와 백엔드를 하나의 프로세스로 합친다.

### 변경 사항
- **Frontend**: `npm run build` 실행 → `frontend/dist` 생성
- **Backend**:
  - `frontend/dist`의 내용을 `backend/app/static` (또는 유사 경로)으로 복사
  - FastAPI에서 `/` 경로 접속 시 `index.html` 반환 (SPA 라우팅 처리 포함)
  - API는 `/api` 프리픽스 유지

### 핵심 외부 의존성

| 의존성 | 용도 | 비고 |
|---|---|---|
| `ffmpeg` | 스트림 녹화 및 변환 | 모든 플랫폼에서 필수 |
| `streamlink` | 치지직 스트림 URL 추출 | 모든 플랫폼에서 필수 |

---

## 2. Docker 배포 (Universal)

가장 우선순위가 높으며, Linux(Ubuntu, Debian, Arch 등) 및 NAS 사용자에게 적합하다.

### Dockerfile 구조 (Multi-stage Build)
1.  **Build Stage (Node)**: `node:20-alpine` 기반. `npm install` & `npm run build` 수행.
2.  **Runtime Stage (Python)**: `python:3.12-slim` 기반.
    - **시스템 패키지 설치**: `apt-get install -y ffmpeg streamlink`
    - **Python 패키지**: `requirements.txt` 설치
    - **파일 복사**: Stage 1의 빌드 결과물을 가져옴
    - **실행**: `uvicorn`으로 서버 구동

### Docker Compose
- `docker-compose.yml` 제공
- **볼륨 마운트**:
  - `./recordings` - 녹화 파일 저장소
  - `./data` - `channels.json` 등 설정 파일 영속성 보장
  - `./logs` - 애플리케이션 로그
- **포트 포워딩**: `8000:8000`
- **환경 변수 (`.env` 파일 연동)**:
  - `APP_PORT` - 서버 포트 (기본값: `8000`)
  - `RECORDINGS_DIR` - 녹화 파일 저장 경로
  - `LOG_LEVEL` - 로그 레벨 (기본값: `INFO`)

---

## 3. Windows Desktop 배포

일반 사용자를 위해 Python이나 Node.js 설치 없이 실행 파일 하나로 동작하게 한다.

### 도구: PyInstaller
- Python 인터프리터와 의존성 라이브러리를 하나의 `.exe` (또는 폴더)로 묶음.

### 외부 바이너리 처리 (FFmpeg & Streamlink)
- **옵션 A (내장)**: `ffmpeg.exe`, `streamlink` 관련 바이너리를 빌드 폴더에 포함. (용량 증가, 사용자 편의성 높음)
- **옵션 B (외장)**: 사용자가 직접 설치하거나 같은 폴더에 넣도록 안내.
- **결정**: "Pro" 버전에 걸맞게 **옵션 A(내장)** 방식을 기본으로 하되, 설정에서 경로 변경 가능하도록 유지.

### 실행 흐름
1. 사용자가 `ChzzkRecorder.exe` 실행
2. 백엔드 서버(Uvicorn)가 백그라운드(또는 최소화된 콘솔)에서 시작
3. 서버 시작 후 자동으로 기본 브라우저를 열어 `http://localhost:8000` 접속 (Python `webbrowser` 모듈 활용)
4. **시스템 트레이 아이콘** (`pystray` 사용): 앱 종료, 브라우저 재열기, 상태 표시 기능 제공

---

## 4. Linux Native 배포 (Ubuntu 및 타 배포판)

Docker를 사용하지 않는 리눅스 환경(LXC 컨테이너, 저사양 VPS 등)을 지원한다.
특정 배포판 패키지(.deb, .rpm)보다는 **범용 쉘 스크립트** 방식을 사용한다.

### 설치 스크립트 (`install.sh`)
1. **사전 요구사항 확인**: `python3.10+`, `ffmpeg`, `streamlink`, `git` 설치 여부 확인 및 안내.
2. **가상환경 생성**: `python3 -m venv venv`
3. **의존성 설치**: `venv/bin/pip install -r requirements.txt`
4. **프론트엔드 빌드**: Release Asset에 미리 빌드된 정적 파일 포함하여 배포 *(권장)*

### 서비스 등록 (`setup_service.sh`)
- `systemd` 서비스 파일 생성 (`/etc/systemd/system/signal-recorder.service`)
- 부팅 시 자동 실행, 로그 관리(`journalctl`) 지원
- **범용성**: Systemd를 사용하는 대부분의 최신 리눅스 배포판(Ubuntu, Debian, CentOS 7+, Fedora, Arch)에서 호환됨.

---

## 5. 버전 관리 및 릴리즈 정책

### 버전 규칙 (Semantic Versioning)
- `MAJOR.MINOR.PATCH` 형식 사용 (예: `v1.0.0`)
  - **MAJOR**: 호환되지 않는 API 변경 또는 대규모 구조 변경
  - **MINOR**: 하위 호환 기능 추가
  - **PATCH**: 버그 수정

### GitHub Release 절차
1. `main` 브랜치에 최종 변경사항 머지
2. Git 태그 생성: `git tag -a v1.0.0 -m "Release v1.0.0"`
3. GitHub Release 페이지에 다음 Asset 첨부:
   - `ChzzkRecorder-v1.0.0-windows-x64.zip` (`.exe` + 내장 바이너리)
   - `signal-recorder-v1.0.0-linux.tar.gz` (설치 스크립트 포함)
   - `CHANGELOG.md` 업데이트 내용 릴리즈 노트에 반영

### CHANGELOG 관리
- `docs/CHANGELOG.md` 파일로 별도 관리
- 각 버전별 **Added / Fixed / Changed / Removed** 섹션으로 구성

---

## 작업 순서 (Checklist)

### Step 1: 통합 구조 준비
- [x] `backend/app/main.py`: SPA(Single Page Application) 서빙을 위한 StaticFiles 및 HTMLResponse 설정 추가
- [x] `frontend/vite.config.ts`: 빌드 출력 경로 조정 (`../backend/app/static`)
- [x] `.env.example` 파일 작성 (환경 변수 템플릿 제공)

### Step 2: Docker화
- [x] `Dockerfile` 작성 (Multi-stage, `ffmpeg` + `streamlink` 포함)
- [x] `docker-compose.yml` 작성 (볼륨 및 `.env` 연동)
- [ ] 로컬 Docker 빌드 및 실행 테스트

### Step 3: Windows 패키징
- [x] `backend/run.py` 수정: 실행 시 브라우저 자동 오픈 로직 추가 (`--desktop` 플래그)
- [x] `pystray` 연동: 시스템 트레이 아이콘 구현 (종료, 브라우저 열기)
- [x] `signal_recorder.spec` 파일 작성 (데이터 파일, `ffmpeg.exe`, `streamlink`, 정적 파일 포함 설정, onedir 방식)
- [ ] `.exe` 빌드 및 클린 윈도우 환경 테스트

### Step 4: Linux 스크립트
- [x] `scripts/install.sh` 작성 (`streamlink` 사전 요구사항 확인 포함)
- [x] `scripts/signal-recorder.service` 템플릿 작성
- [x] `scripts/setup_service.sh` 작성

### Step 5: 릴리즈
- [x] `docs/CHANGELOG.md` 초안 작성
- [ ] GitHub Release용 Asset 패키징 및 업로드
- [ ] README.md의 설치 방법 섹션 업데이트