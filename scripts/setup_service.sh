#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Signal-Recorder systemd 서비스 등록 스크립트
# 사용: sudo bash scripts/setup_service.sh [설치경로] [실행사용자]
# 예시: sudo bash scripts/setup_service.sh /opt/signal-recorder myuser
# ─────────────────────────────────────────────────────────────
set -e

INSTALL_DIR="${1:-/opt/signal-recorder}"
RUN_USER="${2:-$(logname 2>/dev/null || echo 'ubuntu')}"
SERVICE_NAME="signal-recorder"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}@.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'
NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC}  $1"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "이 스크립트는 sudo로 실행해야 합니다."
    exit 1
fi

log_info "서비스 파일 복사 중: $SERVICE_FILE"
# 설치 경로와 실제 경로로 치환
sed \
    -e "s|/opt/signal-recorder|$INSTALL_DIR|g" \
    "$SCRIPT_DIR/signal-recorder.service" > "$SERVICE_FILE"

log_info "systemd 데몬 리로드..."
systemctl daemon-reload

log_info "서비스 활성화 및 시작 (사용자: $RUN_USER)"
systemctl enable --now "${SERVICE_NAME}@${RUN_USER}"

echo ""
echo -e "${GREEN}✅ 서비스 등록 완료!${NC}"
echo ""
echo "  상태 확인:  sudo systemctl status ${SERVICE_NAME}@${RUN_USER}"
echo "  로그 보기:  sudo journalctl -u ${SERVICE_NAME}@${RUN_USER} -f"
echo "  서비스 중지: sudo systemctl stop ${SERVICE_NAME}@${RUN_USER}"
echo ""
