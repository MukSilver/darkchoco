#!/usr/bin/env bash
# 새 서버에 RAG DB 를 한 번 설치한다 (Ubuntu, 메모리 1GB 기준). root 로 돌린다.
#
#   sudo bash setup.sh
#
# 하는 일: 예비 메모리(스왑) 2GB, 필요한 꾸러미, ragdb 사용자, 저장소 받기, 가상환경, 질의 서버 자동 실행 등록.
# 하지 않는 일: .env 넣기, 판 만들기(refresh.py), 터널, 주간 예약. 열쇠가 있어야 하는 일이라 README 의 순서대로 손으로 한다.
# 여러 번 돌려도 된다. 이미 된 것은 건너뛴다.
set -euo pipefail

REPO="https://github.com/MukSilver/darkchoco"
DEST="/opt/darkchoco"
APP="$DEST/apps/ragdb"

[ "$(id -u)" = "0" ] || { echo "root 로 돌린다: sudo bash setup.sh"; exit 1; }

# 1. 예비 메모리. 질의 서버가 600MB 쯤 쓰고 주간 배치도 그만큼 쓴다. 1GB 서버에서 둘이 겹치면 모자란다
if ! swapon --show | grep -q '/swapfile'; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=10
  grep -q '^vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

# 2. 꾸러미
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git python3 python3-venv python3-pip ca-certificates curl

# node 는 화면을 구워 올릴 때만 쓴다 (deploy/publish.sh). 우분투 기본 꾸러미의 node 는 낡아서 화면 도구(Vite, wrangler)가 돌지 않는다.
# 22 판을 NodeSource 꾸러미 저장소에서 받는다
if ! command -v node >/dev/null 2>&1 || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 22 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

# 3. 사용자. 로그인 껍데기 없이, 권한 낮게
id ragdb >/dev/null 2>&1 || useradd --system --create-home --home-dir /home/ragdb --shell /usr/sbin/nologin ragdb
mkdir -p /var/log/ragdb
chown ragdb:ragdb /var/log/ragdb

# 4. 저장소
if [ ! -d "$DEST/.git" ]; then
  git clone "$REPO" "$DEST"
fi
chown -R ragdb:ragdb "$DEST"

# 5. 가상환경과 의존성
sudo -u ragdb -H bash -c "cd '$APP' && python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip && .venv/bin/python -m pip install -r requirements.txt"

# 6. 질의 서버 자동 실행. .env 와 판이 아직 없으므로 등록만 하고 띄우지는 않는다
cp "$APP/deploy/ragdb-api.service" /etc/systemd/system/ragdb-api.service
systemctl daemon-reload
systemctl enable ragdb-api.service

chmod +x "$APP/deploy/publish.sh"

cat <<'EOF'

설치 끝. 이어서 할 일 (deploy/README.md 의 2번부터):
  1) /opt/darkchoco/apps/ragdb/.env 를 넣는다 (권한 600, 주인 ragdb)
  2) sudo -u ragdb -H bash -c 'cd /opt/darkchoco/apps/ragdb && .venv/bin/python scripts/check_keys.py && .venv/bin/python scripts/refresh.py'
  3) systemctl start ragdb-api && curl -s http://127.0.0.1:8787/api/status
  4) cloudflared 터널, 화면 올리기, 주간 예약
EOF
