#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Signal Recorder — Linux Native 설치 스크립트
#  사용법 (원라이너):
#    curl -fsSL https://raw.githubusercontent.com/eruminyu/Signal-Recorder/main/scripts/install.sh | bash
#
#  지원 OS: Ubuntu 20.04+, Debian 11+, CentOS/RHEL 8+, Fedora 36+, Arch Linux
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

# ── 색상 & 아이콘 ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

REPO_URL="https://github.com/eruminyu/Signal-Recorder.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/signal-recorder}"
REQUIRED_PYTHON_MINOR=10   # 3.10+

# ── 출력 헬퍼 ─────────────────────────────────────────────────
info()    { echo -e "${GREEN}[✔]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✘]${NC} $1"; exit 1; }
step()    { echo -e "\n${BOLD}${CYAN}▶ $1${NC}"; }
banner()  {
  echo ""
  echo -e "${CYAN}${BOLD}"
  echo "  ██████╗██╗  ██╗███████╗███████╗██╗  ██╗"
  echo " ██╔════╝██║  ██║╚══███╔╝╚══███╔╝██║ ██╔╝"
  echo " ██║     ███████║  ███╔╝   ███╔╝ █████╔╝ "
  echo " ██║     ██╔══██║ ███╔╝   ███╔╝  ██╔═██╗ "
  echo " ╚██████╗██║  ██║███████╗███████╗██║  ██╗"
  echo "  ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝"
  echo -e "${NC}${BOLD}   Recorder Pro — Linux Native Installer${NC}"
  echo ""
}

# ── OS 감지 ───────────────────────────────────────────────────
detect_os() {
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_ID_LIKE="${ID_LIKE:-}"
  else
    error "지원하지 않는 OS입니다. /etc/os-release 파일이 없습니다."
  fi

  # Debian 계열 (Ubuntu, Debian, Linux Mint, Pop!_OS, ...)
  if echo "$OS_ID $OS_ID_LIKE" | grep -qiE "ubuntu|debian"; then
    PKG_MANAGER="apt"
  # RHEL 계열 (CentOS, AlmaLinux, Rocky, Fedora, ...)
  elif echo "$OS_ID $OS_ID_LIKE" | grep -qiE "fedora|rhel|centos|almalinux|rocky"; then
    if command -v dnf &>/dev/null; then PKG_MANAGER="dnf"; else PKG_MANAGER="yum"; fi
  # Arch 계열
  elif echo "$OS_ID $OS_ID_LIKE" | grep -qi "arch"; then
    PKG_MANAGER="pacman"
  else
    PKG_MANAGER="unknown"
    warn "알 수 없는 OS (${OS_ID}). 수동으로 의존성을 설치해야 할 수 있습니다."
  fi
  info "OS 감지 완료: ${PRETTY_NAME:-$OS_ID} (패키지 매니저: $PKG_MANAGER)"
}

# ── 패키지 설치 헬퍼 ──────────────────────────────────────────
pkg_install() {
  local pkg="$1"
  case "$PKG_MANAGER" in
    apt)    sudo apt-get install -y "$pkg" ;;
    dnf)    sudo dnf install -y "$pkg" ;;
    yum)    sudo yum install -y "$pkg" ;;
    pacman) sudo pacman -S --noconfirm "$pkg" ;;
    *)      error "패키지 매니저를 알 수 없어 $pkg 를 설치할 수 없습니다. 수동 설치 후 다시 실행하세요." ;;
  esac
}

# ── 1. 시스템 의존성 설치 ─────────────────────────────────────
install_dependencies() {
  step "시스템 의존성 확인 및 설치"

  # git
  if ! command -v git &>/dev/null; then
    info "git 설치 중..."
    pkg_install git
  fi
  info "git $(git --version | awk '{print $3}') ✓"

  # curl
  if ! command -v curl &>/dev/null; then
    info "curl 설치 중..."
    pkg_install curl
  fi
  info "curl ✓"

  # ffmpeg 설치
  # Ubuntu/Debian: apt 기본(6.x) 사용 — Streamlink 파이프 모드 기준으로 6.x로 충분
  # 그 외 OS: BtbN 정적 빌드 fallback
  _install_ffmpeg_static() {
    local arch pattern
    arch=$(uname -m)
    case "$arch" in
      x86_64)  pattern="linux64-gpl.tar.xz" ;;
      aarch64) pattern="linuxarm64-gpl.tar.xz" ;;
      *)       error "지원하지 않는 CPU 아키텍처: $arch (x86_64/aarch64 만 지원)" ;;
    esac

    info "BtbN/FFmpeg-Builds 최신 릴리즈 조회 중..."
    local url
    url=$(curl -fsSL "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest" \
      | grep "browser_download_url" \
      | grep "$pattern" \
      | grep -v "shared" \
      | cut -d'"' -f4 \
      | head -1)
    [ -z "$url" ] && error "ffmpeg 다운로드 URL 조회 실패.\n  수동: https://github.com/BtbN/FFmpeg-Builds/releases"

    local tmpdir
    tmpdir=$(mktemp -d)
    trap "rm -rf '$tmpdir'" EXIT

    info "ffmpeg 정적 빌드 다운로드 중 ($arch)..."
    curl -fsSL --retry 3 -L -o "$tmpdir/ffmpeg.tar.xz" "$url" \
      || error "ffmpeg 다운로드 실패."

    info "압축 해제 중..."
    tar xf "$tmpdir/ffmpeg.tar.xz" -C "$tmpdir"

    local ffmpeg_bin ffprobe_bin
    ffmpeg_bin=$(find "$tmpdir" -type f -name "ffmpeg" | head -1)
    ffprobe_bin=$(find "$tmpdir" -type f -name "ffprobe" | head -1)
    [ -z "$ffmpeg_bin" ] && error "ffmpeg 압축 해제 실패."

    sudo install -m 755 "$ffmpeg_bin" /usr/local/bin/ffmpeg
    [ -n "$ffprobe_bin" ] && sudo install -m 755 "$ffprobe_bin" /usr/local/bin/ffprobe
    trap - EXIT
    rm -rf "$tmpdir"
  }

  if ! command -v ffmpeg &>/dev/null; then
    if [ "$PKG_MANAGER" = "apt" ]; then
      info "ffmpeg 설치 중 (apt)..."
      sudo apt-get install -y ffmpeg
    else
      info "ffmpeg 정적 빌드 설치 중..."
      _install_ffmpeg_static
    fi
  fi

  # 최소 버전 검증: ffmpeg 6.0+
  _FFMPEG_VER=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
  _FFMPEG_MAJOR=$(echo "$_FFMPEG_VER" | sed 's/^[nN]//' | cut -d. -f1)
  if [ -z "$_FFMPEG_MAJOR" ] || ! [ "$_FFMPEG_MAJOR" -eq "$_FFMPEG_MAJOR" ] 2>/dev/null || [ "$_FFMPEG_MAJOR" -lt 6 ]; then
    error "ffmpeg 6.0 이상이 필요합니다 (현재: ${_FFMPEG_VER:-알 수 없음}).\n  sudo apt install ffmpeg 로 설치하세요."
  fi
  info "ffmpeg ${_FFMPEG_VER} ✓"

  # Python 3.10+
  PYTHON_CMD=""
  for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
      VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
      MINOR=$(echo "$VER" | cut -d. -f2)
      if [ "$MINOR" -ge "$REQUIRED_PYTHON_MINOR" ]; then
        PYTHON_CMD="$cmd"
        info "Python $VER ✓ ($cmd)"
        break
      fi
    fi
  done

  if [ -z "$PYTHON_CMD" ]; then
    info "Python 3.12 설치 중..."
    if [ "$PKG_MANAGER" = "apt" ]; then
      sudo apt-get update -qq
      sudo apt-get install -y software-properties-common
      sudo add-apt-repository -y ppa:deadsnakes/ppa
      sudo apt-get update -qq
      sudo apt-get install -y python3.12 python3.12-venv python3.12-distutils
    elif [ "$PKG_MANAGER" = "dnf" ]; then
      sudo dnf install -y python3.12
    else
      error "Python 3.10+ 를 찾을 수 없습니다. 수동으로 설치 후 다시 실행하세요.\n  https://www.python.org/downloads/"
    fi
    PYTHON_CMD="python3.12"
    info "Python 3.12 설치 완료 ✓"
  else
    # Python은 있지만 venv 패키지가 없을 수 있음 (Ubuntu deadsnakes 등)
    if [ "$PKG_MANAGER" = "apt" ]; then
      PY_MINOR=$("$PYTHON_CMD" -c 'import sys; print(sys.version_info.minor)')
      PY_VENV_PKG="python3.${PY_MINOR}-venv"
      if ! "$PYTHON_CMD" -c 'import ensurepip' 2>/dev/null; then
        info "${PY_VENV_PKG} 설치 중..."
        sudo apt-get install -y "$PY_VENV_PKG" 2>/dev/null || \
          sudo apt-get install -y python3-venv
        info "venv 패키지 설치 완료 ✓"
      fi
    fi
  fi

  # Node.js 18+ (프론트엔드 빌드용)
  NODE_OK=false
  if command -v node &>/dev/null; then
    NODE_VER=$(node -e 'process.stdout.write(process.versions.node)')
    NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
      NODE_OK=true
      info "Node.js v$NODE_VER ✓"
    fi
  fi

  if [ "$NODE_OK" = "false" ]; then
    info "Node.js 22 LTS 설치 중 (NodeSource)..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - 2>/dev/null || \
    curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo bash - 2>/dev/null || \
    error "Node.js 설치 실패. https://nodejs.org 에서 수동 설치하세요."
    pkg_install nodejs || error "Node.js 설치 실패"
    info "Node.js $(node --version) ✓"
  fi
}

# ── 2. 저장소 클론 ────────────────────────────────────────────
clone_repo() {
  step "저장소 클론"

  if [ -d "$INSTALL_DIR/.git" ]; then
    warn "이미 설치된 저장소가 있습니다: $INSTALL_DIR"
    warn "최신 버전으로 업데이트합니다..."
    git -C "$INSTALL_DIR" fetch origin && git -C "$INSTALL_DIR" reset --hard origin/main
  else
    info "저장소를 $INSTALL_DIR 에 클론 중..."
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
  info "저장소 준비 완료 ✓"
}

# ── 3. 프론트엔드 빌드 ─────────────────────────────────────────
build_frontend() {
  step "프론트엔드 빌드 (React → 정적 파일)"

  cd "$INSTALL_DIR/frontend"
  info "npm ci 실행 중..."
  npm ci --silent
  info "npm run build 실행 중..."
  # vite.config.ts의 outDir이 '../backend/app/static'으로 설정되어 있어
  # 빌드 결과물이 자동으로 backend/app/static 에 직접 생성됨
  npm run build
  info "프론트엔드 빌드 완료 ✓"
  cd "$INSTALL_DIR"
}

# ── 4. Python 가상환경 & 의존성 ───────────────────────────────
setup_python() {
  step "Python 가상환경 설정"

  VENV_DIR="$INSTALL_DIR/.venv"
  "$PYTHON_CMD" -m venv "$VENV_DIR"
  info "가상환경 생성 완료: $VENV_DIR"

  info "pip 업데이트 중..."
  "$VENV_DIR/bin/pip" install --upgrade pip -q

  info "Python 의존성 설치 중..."
  "$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/backend/requirements.txt" -q
  info "Python 의존성 설치 완료 ✓"
}

# ── 5. 데이터 디렉토리 생성 ──────────────────────────────────
setup_dirs() {
  step "데이터 디렉토리 생성"
  mkdir -p "$INSTALL_DIR/recordings" "$INSTALL_DIR/data" "$INSTALL_DIR/logs"
  info "디렉토리 생성 완료 ✓"
}

# ── 6. 실행 스크립트 생성 ─────────────────────────────────────
create_launcher() {
  step "실행 스크립트 생성"

  LAUNCHER="$INSTALL_DIR/start.sh"
  cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
# Signal Recorder 실행 스크립트
cd "$(dirname "\$(realpath "\$0")")/backend"
exec "../.venv/bin/python" run.py "\$@"
EOF
  chmod +x "$LAUNCHER"
  info "실행 스크립트 생성 완료: $LAUNCHER ✓"
}

# systemd 서비스 등록 여부 (자동 실행 스킵 판단용)
SERVICE_REGISTERED=false

# ── 7. systemd 서비스 설치 (선택) ────────────────────────────
install_service() {
  if ! command -v systemctl &>/dev/null; then
    warn "systemd를 찾을 수 없습니다. 서비스 설치를 건너뜁니다."
    return 0
  fi

  # 이미 서비스가 등록되어 있으면 재등록 질문 없이 자동 재시작
  if systemctl is-active --quiet signal-recorder 2>/dev/null; then
    info "기존 서비스 감지 — 업데이트 후 자동 재시작합니다."
    sudo systemctl daemon-reload
    sudo systemctl restart signal-recorder
    SERVICE_REGISTERED=true
    info "서비스 재시작 완료 ✓"
    info "서비스 상태: sudo systemctl status signal-recorder"
    return 0
  fi

  echo ""
  # 신규 설치: curl | bash 파이프 환경에서는 stdin을 /dev/tty로 강제 연결
  read -rp "$(echo -e "${YELLOW}[?]${NC} systemd 서비스로 등록하시겠습니까? (부팅 시 자동 실행) [y/N]: ")" REPLY </dev/tty
  if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    SERVICE_FILE="/etc/systemd/system/signal-recorder.service"
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Signal Recorder - Live Stream Recorder
Documentation=https://github.com/eruminyu/Signal-Recorder
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$INSTALL_DIR/backend
ExecStart=$INSTALL_DIR/.venv/bin/python run.py
Restart=on-failure
RestartSec=10
StandardOutput=append:$INSTALL_DIR/logs/service.log
StandardError=append:$INSTALL_DIR/logs/service-error.log

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable signal-recorder
    sudo systemctl start signal-recorder
    SERVICE_REGISTERED=true
    info "systemd 서비스 등록 및 시작 완료 ✓"
    info "서비스 상태: sudo systemctl status signal-recorder"
  else
    info "서비스 등록을 건너뜁니다."
  fi
}

# ── 완료 메시지 ──────────────────────────────────────────────
print_done() {
  echo ""
  echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}${BOLD}║      🎉 설치가 완료되었습니다!             ║${NC}"
  echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════╝${NC}"
  echo ""
  echo -e "  ${BOLD}▶ 수동 실행:${NC}"
  echo -e "    ${CYAN}$INSTALL_DIR/start.sh${NC}"
  echo ""
  echo -e "  ${BOLD}▶ 접속 주소:${NC}"
  echo -e "    ${CYAN}http://localhost:8000${NC}  (로컬)"
  LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
  if [ -n "$LOCAL_IP" ]; then
    echo -e "    ${CYAN}http://$LOCAL_IP:8000${NC}  (원격)"
  fi
  echo ""
  echo -e "  ${BOLD}▶ 서비스 관리 (설치한 경우):${NC}"
  echo -e "    sudo systemctl status signal-recorder"
  echo -e "    sudo systemctl stop   signal-recorder"
  echo -e "    sudo systemctl restart signal-recorder"
  echo ""
  echo -e "  ${BOLD}▶ 로그 확인:${NC}"
  echo -e "    tail -f ${CYAN}$INSTALL_DIR/logs/service.log${NC}"
  echo ""
}

# ── 메인 ──────────────────────────────────────────────────────
main() {
  banner

  # root로 실행 방지 (서비스 설치 단계에서만 sudo 사용)
  if [ "$EUID" -eq 0 ]; then
    warn "root로 실행 중입니다. 프로덕션 환경에서는 전용 사용자 계정 사용을 권장합니다."
  fi

  detect_os
  install_dependencies
  clone_repo
  build_frontend
  setup_python
  setup_dirs
  create_launcher
  install_service
  print_done

  # systemd 서비스로 이미 시작된 경우 중복 실행 방지
  if [ "$SERVICE_REGISTERED" = "true" ]; then
    info "systemd 서비스로 실행 중입니다. 별도 실행을 건너뜁니다."
  else
    step "서버 시작"
    info "Signal Recorder 를 시작합니다..."
    exec "$INSTALL_DIR/start.sh"
  fi
}

main "$@"
