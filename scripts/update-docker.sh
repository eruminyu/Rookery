#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Signal Recorder — Docker 업데이트 스크립트
#  사용법 (원라이너):
#    curl -fsSL https://raw.githubusercontent.com/eruminyu/Signal-Recorder/main/scripts/update-docker.sh | bash
#
#  또는 설치 디렉토리에서 직접 실행:
#    ~/signal-recorder/scripts/update-docker.sh
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

INSTALL_DIR="${INSTALL_DIR:-$HOME/signal-recorder}"

info()  { echo -e "${GREEN}[✔]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✘]${NC} $1"; exit 1; }
step()  { echo -e "\n${BOLD}${CYAN}▶ $1${NC}"; }

# ── Docker Compose 명령어 감지 ────────────────────────────────
detect_compose() {
  if docker info &>/dev/null 2>&1; then
    DOCKER_SUDO=""
  else
    DOCKER_SUDO="sudo"
  fi

  if $DOCKER_SUDO docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="$DOCKER_SUDO docker compose"
  elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="$DOCKER_SUDO docker-compose"
  else
    error "Docker Compose를 찾을 수 없습니다."
  fi
}

# ── 설치 디렉토리 확인 ────────────────────────────────────────
check_install() {
  if [ ! -d "$INSTALL_DIR/.git" ]; then
    error "설치 디렉토리를 찾을 수 없습니다: $INSTALL_DIR\n  먼저 install-docker.sh로 설치해 주세요."
  fi
  info "설치 디렉토리 확인: $INSTALL_DIR ✓"
}

# ── 1. 최신 코드 pull ─────────────────────────────────────────
pull_latest() {
  step "최신 코드 가져오기"
  git -C "$INSTALL_DIR" fetch origin
  LOCAL=$(git -C "$INSTALL_DIR" rev-parse HEAD)
  REMOTE=$(git -C "$INSTALL_DIR" rev-parse origin/main)
  if [ "$LOCAL" = "$REMOTE" ]; then
    info "이미 최신 버전입니다. 업데이트를 건너뜁니다."
    exit 0
  fi
  git -C "$INSTALL_DIR" pull --ff-only origin main
  info "코드 업데이트 완료 ✓"
}

# ── 2. 컨테이너 재빌드 & 재시작 ──────────────────────────────
rebuild_container() {
  step "Docker 이미지 재빌드 및 컨테이너 재시작"
  cd "$INSTALL_DIR"

  # 기존 컨테이너 중지
  $COMPOSE_CMD down
  info "기존 컨테이너 중지 완료 ✓"

  # 이미지 재빌드 후 시작
  info "Docker 이미지 재빌드 중..."
  $COMPOSE_CMD up --build -d
  info "컨테이너 재시작 완료 ✓"

  # 헬스체크 대기
  PORT=$(grep -E '^\s*-\s*"[0-9]+:8000"' "$INSTALL_DIR/docker-compose.yml" 2>/dev/null | grep -oE '^[0-9]+' | head -1 || echo "8000")
  echo -n "  서버 시작 대기 중"
  for i in $(seq 1 20); do
    if curl -sf "http://localhost:${PORT}/health" &>/dev/null; then
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
  echo -e "${GREEN}${BOLD}║   🐳 Docker 업데이트가 완료되었습니다!     ║${NC}"
  echo -e "${GREEN}${BOLD}╚════════════════════════════════════════════╝${NC}"
  echo ""
  LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
  echo -e "  ${BOLD}▶ 접속 주소:${NC}"
  echo -e "    ${CYAN}http://localhost:8000${NC}"
  [ -n "$LOCAL_IP" ] && echo -e "    ${CYAN}http://$LOCAL_IP:8000${NC}  (원격)"
  echo ""
  echo -e "  ${BOLD}▶ 컨테이너 관리:${NC}"
  echo -e "    cd ${CYAN}$INSTALL_DIR${NC}"
  echo -e "    $COMPOSE_CMD logs -f    ${BOLD}# 로그 확인${NC}"
  echo -e "    $COMPOSE_CMD stop       ${BOLD}# 중지${NC}"
  echo ""
}

main() {
  echo ""
  echo -e "${CYAN}${BOLD}  Signal Recorder — Docker 업데이트${NC}"
  echo ""
  detect_compose
  check_install
  pull_latest
  rebuild_container
  print_done
}

main "$@"
