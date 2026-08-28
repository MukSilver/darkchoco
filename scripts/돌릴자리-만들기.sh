#!/usr/bin/env bash
# 크롤러를 돌릴 자리를 만듭니다. Debian · Ubuntu · Kali 에서 됩니다.
# VM 안에서도 WSL 안에서도 같습니다.
#
#     bash scripts/돌릴자리-만들기.sh
#
# 하는 일 — tor 를 깔고, torrc 에 우리 규칙을 넣고, 띄우고, 실제로
# 나가 보고, 파이썬 부품을 깝니다. 마지막에 점검까지 합니다.
#
# **이 스크립트는 노션 토큰을 안 만집니다.** 그것은 사람이 넣습니다.

set -uo pipefail

터널포트="${DARKCHOCO_TOR_PORT:-9080}"
여기="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

파랑() { printf '\n\033[1m%s\033[0m\n' "$*"; }
확인() { printf '  \033[32mOK\033[0m %s\n' "$*"; }
문제() { printf '  \033[31m!!\033[0m %s\n' "$*"; }
그냥() { printf '     %s\n' "$*"; }

내가루트인가() { [ "$(id -u)" = "0" ]; }
관리자() { if 내가루트인가; then "$@"; else sudo "$@"; fi; }

# ── 1. 어디인지 봅니다 ──────────────────────────────────────────────
파랑"1. 여기가 어디인가"
if grep -qi microsoft /proc/version 2>/dev/null; then
    자리="WSL"
    그냥 "WSL 입니다. 파일시스템은 나뉘지만 **망은 호스트를 지납니다.**"
    그냥 "/mnt/c 로 윈도우 파일이 그대로 보입니다. 격리가 아니라 칸막이입니다."
    그냥 "평소에는 VirtualBox VM 을 쓰십시오."
elif [ -d /proc/xen ] || grep -qiE "virtualbox|vmware|kvm|qemu" /sys/class/dmi/id/product_name 2>/dev/null; then
    자리="VM"
    확인 "VM 입니다. $(cat /sys/class/dmi/id/product_name 2>/dev/null)"
else
    자리="맨기계"
    문제 "가상 머신이 아닌 것 같습니다. 다크웹 쪽이 이 기기로 내려옵니다."
    그냥 "그래도 계속하려면 10초 안에 아무 키나 누르십시오."
    read -r -t 10 -n 1 || { 그냥 "멈췄습니다."; exit 1; }
fi

# ── 2. tor ─────────────────────────────────────────────────────────
파랑 "2. tor"
if command -v tor >/dev/null 2>&1; then
    확인 "이미 깔려 있습니다 — $(tor --version 2>/dev/null | head -1)"
else
    그냥 "받습니다..."
    export DEBIAN_FRONTEND=noninteractive
    관리자 apt-get update -qq || { 문제 "apt update 실패"; exit 1; }
    관리자 apt-get install -y -qq tor || { 문제 "tor 설치 실패"; exit 1; }
    확인 "깔았습니다 — $(tor --version 2>/dev/null | head -1)"
fi

# ── 3. torrc ───────────────────────────────────────────────────────
파랑 "3. torrc 에 우리 규칙 넣기"
설정=/etc/tor/torrc
if 관리자 grep -q "darkchoco" "$설정" 2>/dev/null; then
    확인 "이미 들어 있습니다"
else
    관리자 cp "$설정" "$설정.bak.$(date +%s)" 2>/dev/null || true
    관리자 tee -a "$설정" >/dev/null <<EOF

# ── darkchoco ────────────────────────────────────────────────
# 표준 라이브러리가 SOCKS 를 못 타서 HTTP CONNECT 를 씁니다.
HTTPTunnelPort ${터널포트}

# 한국 출구를 안 씁니다. Tor 에도 한국 출구가 있어서, 안 막으면
# 우리 IP 는 아니어도 한국 주소가 남습니다.
# StrictNodes 가 있어야 이 제외가 지켜집니다.
ExcludeExitNodes {kr}
StrictNodes 1
EOF
    확인 "넣었습니다 (HTTPTunnelPort ${터널포트} · ExcludeExitNodes {kr} · StrictNodes 1)"
fi

# ── 4. 띄우기 ──────────────────────────────────────────────────────
파랑 "4. tor 띄우기"
떴나() { (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -q ":${터널포트}\b"; }

if 떴나; then
    확인 "이미 떠 있습니다"
else
    if command -v systemctl >/dev/null 2>&1 && systemctl is-system-running >/dev/null 2>&1; then
        관리자 systemctl restart tor >/dev/null 2>&1 && 그냥 "systemd 로 띄웁니다"
    fi
    if ! 떴나; then
        그냥 "직접 띄웁니다 (systemd 가 없는 자리입니다)"
        관리자 pkill -x tor 2>/dev/null || true
        sleep 1
        관리자 sh -c "nohup tor -f ${설정} >/tmp/tor.log 2>&1 &"
    fi
    for _ in $(seq 1 30); do 떴나 && break; sleep 1; done
    떴나 && 확인 "${터널포트} 열렸습니다" || { 문제 "${터널포트} 가 안 열립니다. /tmp/tor.log 를 보십시오"; exit 1; }
fi

파랑 "5. 길이 뚫리기를 기다립니다"
그냥 "Tor 가 중계 목록을 받는 데 1~3분 걸립니다."
for i in $(seq 1 120); do
    if grep -q "Bootstrapped 100%" /tmp/tor.log 2>/dev/null \
       || 관리자 grep -q "Bootstrapped 100%" /var/log/tor/log 2>/dev/null; then
        break
    fi
    if [ $((i % 15)) = 0 ]; then
        진행=$( { grep -o "Bootstrapped [0-9]*%" /tmp/tor.log 2>/dev/null || true; } | tail -1)
        그냥 "${진행:-여는 중} ... ($((i * 2))초)"
    fi
    sleep 2
done

# ── 6. 정말 나가지나 ───────────────────────────────────────────────
파랑 "6. 실제로 나가 보기"
답=$(curl -sS --max-time 60 --proxy "http://127.0.0.1:${터널포트}" \
     https://check.torproject.org/api/ip 2>&1)
if printf '%s' "$답" | grep -q '"IsTor":true'; then
    출구=$(printf '%s' "$답" | sed -n 's/.*"IP":"\([^"]*\)".*/\1/p')
    확인 "Tor 를 탑니다. 밖에 남는 주소는 ${출구} 입니다"
else
    문제 "Tor 로 안 나갑니다"
    그냥 "$답"
    그냥 "/tmp/tor.log 를 보십시오. 학교 망이 Tor 를 막을 수 있습니다."
    exit 1
fi

# ── 7. 파이썬 쪽 ───────────────────────────────────────────────────
파랑 "7. 파이썬 부품"
cd "$여기" || exit 1
if [ ! -d .venv ]; then
    python3 -m venv .venv 2>/dev/null || {
        그냥 "python3-venv 를 받습니다..."
        관리자 apt-get install -y -qq python3-venv && python3 -m venv .venv
    }
fi
# shellcheck disable=SC1091
. .venv/bin/activate
pip install -q -e packages && 확인 "부품을 깔았습니다" || 문제 "부품 설치 실패"

# ── 8. 환경 변수 ───────────────────────────────────────────────────
파랑 "8. 환경 변수"
줄="export TOR_SOCKS_PROXY=http://127.0.0.1:${터널포트}"
if grep -qF "$줄" ~/.bashrc 2>/dev/null; then
    확인 "~/.bashrc 에 이미 있습니다"
else
    printf '\n# darkchoco — Tor 를 거쳐 나갑니다\n%s\nexport PYTHONIOENCODING=utf-8\n' "$줄" >> ~/.bashrc
    확인 "~/.bashrc 에 넣었습니다"
fi
export TOR_SOCKS_PROXY="http://127.0.0.1:${터널포트}"
export PYTHONIOENCODING=utf-8

if [ -z "${NOTION_TOKEN:-}" ]; then
    문제 "NOTION_TOKEN 이 없습니다. 노션에 못 씁니다"
    그냥 "~/.bashrc 에 넣으십시오:  export NOTION_TOKEN=..."
    그냥 "**저장소에 넣지 마십시오.** 이 자리에만 둡니다."
else
    확인 "NOTION_TOKEN 있습니다"
fi

# ── 9. 점검 ────────────────────────────────────────────────────────
파랑 "9. 점검"
python dc.py doctor --net 2>&1 | sed -n '/밖으로 나가는 길/,$p' | sed 's/^/  /'

파랑 "다 됐습니다"
그냥 "미리보기      python dc.py crawl --limit 3"
그냥 "실제로 반영    python dc.py crawl --apply"
그냥 "차례표에 걸기  crontab -e 에 아래 한 줄"
그냥 "  */30 * * * * cd $여기 && ./.venv/bin/python dc.py auto >> ~/darkchoco-auto.log 2>&1"
echo
