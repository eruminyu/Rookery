#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Signal Recorder — Docker 설치 스크립트
#  사용법 (원라이너):
#    curl -fsSL https://raw.githubusercontent.com/eruminyu/Signal-Recorder/main/scripts/install-docker.sh | bash
#
#  지원 OS: Ubuntu 20.04+, Debian 11+, CentOS/RHEL 8+, Fedora 36+
#  필요: curl (스크립트 실행에 필요)
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

# ── 색상 & 아이콘 ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

REPO_URL="https://github.com/eruminyu/Signal-Recorder.git"

if [ -z "${INSTALL_DIR:-}" ]; then
  if [ -d "$HOME/chzzk-recorder-pro" ]; then
    INSTALL_DIR="$HOME/chzzk-recorder-pro"
  else
    INSTALL_DIR="$HOME/signal-recorder"
  fi
fi
PORT="${PORT:-8000}"

# ── 출력 헬퍼 ─────────────────────────────────────────────────
info()  { echo -e "${GREEN}[✔]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✘]${NC} $1"; exit 1; }
step()  { echo -e "\n${BOLD}${CYAN}▶ $1${NC}"; }
banner() {
  echo ""
  echo -e "${CYAN}${BOLD}"
  echo "  ██████╗██╗  ██╗███████╗███████╗██╗  ██╗"
  echo " ██╔════╝██║  ██║╚══███╔╝╚══███╔╝██║ ██╔╝"
  echo " ██║     ███████║  ███╔╝   ███╔╝ █████╔╝ "
  echo " ██║     ██╔══██║ ███╔╝   ███╔╝  ██╔═██╗ "
  echo " ╚██████╗██║  ██║███████╗███████╗██║  ██╗"
  echo "  ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝"
  echo -e "${NC}${BOLD}   Recorder Pro — Docker Installer${NC}"
  echo ""
}

# ── OS 감지 ───────────────────────────────────────────────────
detect_os() {
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_ID_LIKE="${ID_LIKE:-}"
  else
    error "지원하지 않는 OS입니다."
  fi

  if echo "$OS_ID $OS_ID_LIKE" | grep -qiE "ubuntu|debian"; then
    PKG_MANAGER="apt"
  elif echo "$OS_ID $OS_ID_LIKE" | grep -qiE "fedora|rhel|centos|almalinux|rocky"; then
    PKG_MANAGER=$(command -v dnf &>/dev/null && echo "dnf" || echo "yum")
  else
    PKG_MANAGER="unknown"
    warn "알 수 없는 OS (${OS_ID}). Docker를 먼저 수동으로 설치해야 할 수 있습니다."
  fi
  info "OS 감지 완료: ${PRETTY_NAME:-$OS_ID}"
}

# ── 1. Docker Engine 설치 ────────────────────────────────────
install_docker() {
  step "Docker Engine 설치 확인"

  if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
    info "Docker $(docker --version | awk '{print $3}' | tr -d ',') 이미 설치됨 ✓"
    return 0
  fi

  warn "Docker가 설치되어 있지 않습니다. Docker 공식 스크립트로 설치합니다..."
  echo ""
  echo -e "  ${YELLOW}Docker 공식 설치 스크립트 (get.docker.com) 를 실행합니다.${NC}"
  read -rp "  계속하시겠습니까? [y/N]: " REPLY
  [[ "$REPLY" =~ ^[Yy]$ ]] || error "설치를 취소했습니다."

  curl -fsSL https://get.docker.com | sudo sh

  # 현재 사용자를 docker 그룹에 추가
  sudo usermod -aG docker "$(whoami)"
  info "Docker 설치 완료 ✓"
  warn "그룹 적용을 위해 로그아웃 후 다시 로그인이 필요할 수 있습니다."
  warn "현재 설치는 'sudo docker' 명령으로 계속 진행합니다."
}

# ── 2. Docker Compose 설치 확인 ──────────────────────────────
install_docker_compose() {
  step "Docker Compose 확인"

  # Docker Compose v2 (플러그인 방식)
  if docker compose version &>/dev/null 2>&1; then
    info "Docker Compose v2 $(docker compose version --short) ✓"
    COMPOSE_CMD="docker compose"
    return 0
  fi

  # 구형 docker-compose (v1) fallback
  if command -v docker-compose &>/dev/null; then
    info "docker-compose $(docker-compose --version | awk '{print $3}' | tr -d ',') ✓"
    COMPOSE_CMD="docker-compose"
    return 0
  fi

  # Docker Compose 플러그인 설치 시도
  info "Docker Compose 플러그인 설치 중..."
  if [ "$PKG_MANAGER" = "apt" ]; then
    sudo apt-get update -qq
    sudo apt-get install -y docker-compose-plugin
  elif [ "$PKG_MANAGER" = "dnf" ]; then
    sudo dnf install -y docker-compose-plugin
  else
    # 바이너리 직접 다운로드
    COMPOSE_VER=$(curl -fsSL https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
    sudo curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VER}/docker-compose-linux-$(uname -m)" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  fi
  COMPOSE_CMD="docker compose"
  info "Docker Compose 설치 완료 ✓"
}

# ── 3. Docker 서비스 시작 ────────────────────────────────────
start_docker_service() {
  step "Docker 서비스 시작"

  if ! sudo systemctl is-active --quiet docker 2>/dev/null; then
    sudo systemctl start docker
    sudo systemctl enable docker
    info "Docker 서비스 시작 완료 ✓"
  else
    info "Docker 서비스 실행 중 ✓"
  fi
}

# ── 4. 저장소 클론 ────────────────────────────────────────────
clone_repo() {
  step "저장소 클론"

  if ! command -v git &>/dev/null; then
    info "git 설치 중..."
    if [ "$PKG_MANAGER" = "apt" ]; then
      sudo apt-get install -y git
    elif [ "$PKG_MANAGER" = "dnf" ] || [ "$PKG_MANAGER" = "yum" ]; then
      sudo "$PKG_MANAGER" install -y git
    else
      error "git을 설치할 수 없습니다. 수동으로 설치 후 다시 실행하세요."
    fi
  fi

  if [ -d "$INSTALL_DIR/.git" ]; then
    warn "이미 설치된 저장소가 있습니다: $INSTALL_DIR"
    warn "최신 버전으로 업데이트합니다..."
    git -C "$INSTALL_DIR" pull --ff-only
  else
    info "저장소를 $INSTALL_DIR 에 클론 중..."
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
  info "저장소 준비 완료 ✓"
}

# ── 5. 데이터 디렉토리 생성 ──────────────────────────────────
setup_dirs() {
  step "데이터 디렉토리 생성"
  mkdir -p "$INSTALL_DIR/recordings" "$INSTALL_DIR/data" "$INSTALL_DIR/logs" "$INSTALL_DIR/config"
  info "디렉토리 생성 완료 ✓"
}

# ── 6. 포트 설정 ──────────────────────────────────────────────
configure_port() {
  step "포트 설정"
  echo ""
  read -rp "$(echo -e "${YELLOW}[?]${NC} 사용할 포트를 입력하세요 [기본값: $PORT]: ")" INPUT_PORT
  if [ -n "$INPUT_PORT" ]; then
    PORT="$INPUT_PORT"
  fi
  info "포트 설정: $PORT ✓"
}

# ── 7. Docker 컨테이너 빌드 & 실행 ───────────────────────────
run_container() {
  step "Docker 이미지 빌드 및 컨테이너 시작"

  cd "$INSTALL_DIR"

  # docker compose 실행 (권한에 따라 sudo 사용)
  if docker info &>/dev/null 2>&1; then
    DOCKER_CMD=""
  else
    DOCKER_CMD="sudo"
  fi

  info "Docker 이미지 빌드 중 (첫 실행 시 수 분 소요)..."
  PORT="$PORT" $DOCKER_CMD $COMPOSE_CMD up --build -d

  info "컨테이너 시작 완료 ✓"

  # 헬스체크 대기
  echo -n "  서버 시작 대기 중"
  for i in $(seq 1 20); do
    if curl -sf "http://localhost:$PORT/health" &>/dev/null; then
      echo ""
      info "서버 응답 확인 ✓"
      break
    fi
    echo -n "."
    sleep 2
  done
  echo ""
}

# ── 완료 메시지 ──────────────────────────────────────────────
print_done() {
  echo ""
  echo -e "${GREEN}${BOLD}╔════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}${BOLD}║      🐳 Docker 배포가 완료되었습니다!      ║${NC}"
  echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════╝${NC}"
  echo ""
  echo -e "  ${BOLD}▶ 접속 주소:${NC}"
  echo -e "    ${CYAN}http://localhost:$PORT${NC}"
  echo -e "    ${CYAN}http://$(hostname -I | awk '{print $1}'):$PORT${NC}  (원격 접속)"
  echo ""
  echo -e "  ${BOLD}▶ 컨테이너 관리:${NC}"
  echo -e "    cd ${CYAN}$INSTALL_DIR${NC}"
  echo -e "    $DOCKER_CMD $COMPOSE_CMD logs -f          ${BOLD}# 로그 확인${NC}"
  echo -e "    $DOCKER_CMD $COMPOSE_CMD stop             ${BOLD}# 중지${NC}"
  echo -e "    $DOCKER_CMD $COMPOSE_CMD up -d            ${BOLD}# 재시작${NC}"
  echo -e "    $DOCKER_CMD $COMPOSE_CMD pull && $DOCKER_CMD $COMPOSE_CMD up -d  ${BOLD}# 업데이트${NC}"
  echo ""
  echo -e "  ${BOLD}▶ 방화벽 (필요한 경우):${NC}"
  echo -e "    sudo ufw allow ${PORT}/tcp"
  echo ""
}

# ── 메인 ──────────────────────────────────────────────────────
main() {
  banner

  if [ "$EUID" -eq 0 ]; then
    warn "root로 실행 중입니다. 프로덕션 환경에서는 전용 사용자 계정 사용을 권장합니다."
  fi

  detect_os
  install_docker
  start_docker_service
  install_docker_compose
  clone_repo
  setup_dirs
  configure_port
  run_container
  print_done
}

main "$@"
