# Linux 서버 설치 가이드

## 📋 개요

Linux 환경에서는 세 가지 방식으로 설치할 수 있습니다:

| 방식 | 대상 | 특징 |
|------|------|------|
| **원라이너 Native** | 서버/NAS (Docker 없이) | 한 줄 명령으로 전체 자동 설치 |
| **원라이너 Docker** | 서버 배포 권장 | 격리 환경, 재현성 보장 |
| **수동 설치** | 개발/고급 사용자 | 직접 제어 |

---

## 🚀 방법 1: 원라이너 — Linux Native (권장: 일반 서버)

터미널에 아래 명령어 하나만 입력하세요.  
OS 감지 → 의존성 설치 → 빌드 → venv 설정 → systemd 등록까지 전부 자동으로 처리합니다.

```bash
curl -fsSL https://raw.githubusercontent.com/eruminyu/Signal-Recorder/main/scripts/install.sh | bash
```

**자동으로 처리되는 것들:**
- ✅ Ubuntu/Debian/CentOS/Fedora/Arch OS 자동 감지
- ✅ Python 3.12, ffmpeg, Node.js 자동 설치
- ✅ 프론트엔드 빌드 (React → 정적 파일)
- ✅ Python 가상환경(.venv) 생성 및 의존성 설치
- ✅ systemd 서비스 등록 (선택, 부팅 시 자동 실행)

> **설치 경로 변경:** 기본 설치 경로는 `~/signal-recorder` 입니다.
> ```bash
> INSTALL_DIR=/opt/signal-recorder curl -fsSL https://raw.githubusercontent.com/eruminyu/Signal-Recorder/main/scripts/install.sh | bash
> ```

---

## 🐳 방법 2: 원라이너 — Docker (권장: 격리 배포)

Docker가 없는 서버에도 사용 가능합니다. Docker Engine 설치까지 자동으로 처리합니다.

```bash
curl -fsSL https://raw.githubusercontent.com/eruminyu/Signal-Recorder/main/scripts/install-docker.sh | bash
```

**자동으로 처리되는 것들:**
- ✅ Docker Engine 자동 설치 (없는 경우)
- ✅ Docker Compose 플러그인 자동 설치
- ✅ 저장소 클론 및 이미지 빌드
- ✅ 컨테이너 백그라운드 실행
- ✅ 헬스체크로 정상 시작 확인

설치 완료 후 출력되는 관리 명령어로 컨테이너를 제어하세요.

---

## 🔧 방법 3: 수동 설치 (고급 사용자)

### 사전 요구사항

```bash
# Ubuntu/Debian 기준
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv ffmpeg git
```

### 설치

```bash
# 저장소 클론
git clone https://github.com/eruminyu/Signal-Recorder.git
cd Signal-Recorder

# 프론트엔드 빌드
cd frontend
npm ci && npm run build
cp -r dist ../backend/app/static
cd ..

# Python 의존성 설치
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 실행

```bash
# 프로젝트 루트에서
source .venv/bin/activate
cd backend
python run.py
```

접속: `http://서버IP:8000`

### 백그라운드 실행 (systemd)

`/etc/systemd/system/signal-recorder.service` 생성:

```ini
[Unit]
Description=Signal Recorder
After=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Signal-Recorder/backend
ExecStart=/home/ubuntu/Signal-Recorder/.venv/bin/python run.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable signal-recorder
sudo systemctl start signal-recorder
sudo systemctl status signal-recorder
```

---

## 🌐 방화벽 설정

원격 접속 시 포트 개방:

```bash
# UFW (Ubuntu)
sudo ufw allow 8000/tcp

# firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

---

## 🧙 초기설정 마법사

설치 후 처음 접속하면 브라우저 기반 마법사가 표시됩니다.

1. `http://서버IP:8000` 접속
2. 마법사 완료 → `.env` 파일 자동 생성
3. 이후 재시작해도 설정 유지

> `.env` 파일을 삭제하면 마법사가 다시 표시됩니다.

---

## 🔄 재설치 / 완전 초기화

재설치 전에 반드시 기존 서비스를 먼저 정리하세요.
**정리하지 않으면 포트 충돌로 서버가 시작되지 않습니다.**

```bash
# 1. systemd 서비스 중지 및 제거
sudo systemctl stop signal-recorder
sudo systemctl disable signal-recorder
sudo rm -f /etc/systemd/system/signal-recorder.service
sudo systemctl daemon-reload

# 2. 설치 디렉토리 삭제
rm -rf ~/signal-recorder

# 3. 재설치
curl -fsSL https://raw.githubusercontent.com/eruminyu/Signal-Recorder/main/scripts/install.sh | bash
```

> ⚠️ **포트가 이미 사용 중이라는 오류가 나는 경우**
> systemd 서비스가 이미 8000 포트를 점유하고 있는 상태입니다.
> 위의 1번 단계(서비스 중지)만 실행 후 재시도하세요.
> ```bash
> sudo systemctl stop signal-recorder
> ```

---

## 🛠️ 트러블슈팅

| 증상 | 해결 |
|------|------|
| `python3.12` 없음 | `sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt install python3.12` |
| `ffmpeg` 명령 없음 | `sudo apt install ffmpeg` |
| 포트 접속 불가 | 방화벽 확인, `sudo ufw allow 8000/tcp` |
| `address already in use` 오류 | `sudo systemctl stop signal-recorder` 후 재실행 |
| Permission denied | `chown -R $USER:$USER ./recordings ./data ./logs` |
| Docker 그룹 권한 오류 | 로그아웃 후 재로그인 (또는 `newgrp docker`) |
