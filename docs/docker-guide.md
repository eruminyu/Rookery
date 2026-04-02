# Docker 가이드

## 개요

Docker 환경에서 Signal-Recorder는 **서버 모드**로 동작합니다.
컨테이너를 올린 뒤, 브라우저로 접속하면 초기설정 마법사가 뜨는 구조입니다.

```
[서버: Docker 컨테이너]  ←  [사용자 PC 브라우저]
    http://서버IP:8000
```

---

## 사전 요구사항

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 설치 (Windows / macOS / Linux)
- Docker Desktop이 실행 중이어야 합니다

---

## 파일 구조

실행 디렉토리에 아래 파일이 필요합니다:

```
📁 프로젝트 폴더/
├── Dockerfile
├── docker-compose.yml
├── backend/
└── frontend/
```

> ⚠️ `config/.env` 파일은 **없어도 됩니다**. 최초 실행 시 마법사가 자동 생성합니다.

---

## 실행 방법

### 1. 이미지 빌드 및 컨테이너 시작

```bash
docker compose up --build
```

> 처음 빌드는 5~10분 소요될 수 있습니다 (ffmpeg 포함).

### 2. 브라우저 접속

```
http://localhost:8000
```

### 3. 초기설정 마법사 완료

- 녹화 저장 경로 설정 (컨테이너 내부 경로: `/app/backend/recordings` 권장)
- 치지직 쿠키 설정 (선택)

마법사 완료 시 설정 파일이 **호스트의 `config/.env`에 자동 생성**됩니다.

### 4. 컨테이너 중단

```bash
docker compose down
```

---

## 재시작 시 (기존 설정 유지 확인)

```bash
docker compose up
```

`config/.env` 파일이 호스트에 남아있으면 마법사 없이 바로 실행됩니다.

---

## 초기화 방법 (처음부터 다시)

```bash
docker compose down
rm config/.env          # Linux/macOS
del config\.env         # Windows
docker compose up
```

---

## 볼륨 구조

| 호스트 경로 | 컨테이너 경로 | 역할 |
|------------|--------------|------|
| `./config` | `/app/config` | 설정 파일 (`.env` 저장 위치) |
| `./recordings` | `/app/backend/recordings` | 녹화 파일 저장 |
| `./data` | `/app/backend/data` | 채널 목록, 다운로드 이력 등 |
| `./logs` | `/app/backend/logs` | 애플리케이션 로그 |

> 💡 녹화 파일 저장 위치를 변경하려면 `docker-compose.yml`에서 호스트 경로를 수정하세요:
> ```yaml
> volumes:
>   - /your/path/recordings:/app/backend/recordings
> ```

---

## 포트 변경

```bash
PORT=9000 docker compose up
```

또는 `docker-compose.yml`에서 직접 수정:

```yaml
ports:
  - "9000:8000"
```

---

## 로그 확인

```bash
docker compose logs -f
```

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 마법사가 계속 뜸 | `config/.env` 볼륨 마운트 실패 | `docker compose down && docker compose up` |
| 녹화 파일이 저장 안 됨 | 볼륨 경로 오류 | `./recordings:/app/backend/recordings` 경로 확인 |
| ffmpeg 오류 | 컨테이너 내 ffmpeg PATH | `FFMPEG_PATH=ffmpeg` 환경변수 확인 |
| 포트 충돌 | 8000번 포트 사용 중 | `PORT=9000 docker compose up` |
