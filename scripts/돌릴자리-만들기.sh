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
#
# 변수와 함수 이름을 영문으로 씁니다. bash 는 한글 이름을 못 받습니다
# (파이썬은 됩니다). 처음에 한글로 썼다가 통째로 안 도는 것을 팀원이
# 쓸 수 있냐는 물음에 시험해 보고서야 알았습니다. 사람에게 보이는
# 글자는 그대로 한글입니다.

set -uo pipefail

PORT="${DARKCHOCO_TOR_PORT:-9080}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TORRC=/etc/tor/torrc
LOG=/tmp/tor-darkchoco.log

step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m!!\033[0m %s\n' "$*"; }
say()  { printf '     %s\n' "$*"; }

as_root() { if [ "$(id -u)" = "0" ]; then "$@"; else sudo "$@"; fi; }

# sudo 가 비밀번호를 물으면 스크립트가 아무 말 없이 멈춥니다. 미리
# 보고 알려 줍니다. 조용히 멈추면 팀원은 뭘 해야 할지 모릅니다.
need_sudo() {
    [ "$(id -u)" = "0" ] && return 0
    if ! command -v sudo >/dev/null 2>&1; then
        bad "sudo 가 없고 root 도 아닙니다. root 로 들어가서 돌리십시오."
        return 1
    fi
    if sudo -n true 2>/dev/null; then
        return 0
    fi
    bad "sudo 가 비밀번호를 묻습니다."
    say "먼저 한 번 넣어 두고 다시 돌리십시오."
    say "    sudo -v && bash scripts/돌릴자리-만들기.sh"
    say "또는 root 로 들어가서 돌리십시오."
    say "    sudo -i"
    return 1
}
listening() { (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -q ":${PORT}[[:space:]]"; }

# ── 1. 어디인지 봅니다 ──────────────────────────────────────────────
step "1. 여기가 어디인가"
if grep -qi microsoft /proc/version 2>/dev/null; then
    say "WSL 입니다. 파일시스템은 나뉘지만 **망은 호스트를 지납니다.**"
    say "/mnt/c 로 윈도우 파일이 그대로 보입니다. 격리가 아니라 칸막이입니다."
    say "평소에는 VirtualBox VM 을 쓰십시오."
elif [ -r /sys/class/dmi/id/product_name ] &&
     grep -qiE "virtualbox|vmware|kvm|qemu|virtual" /sys/class/dmi/id/product_name 2>/dev/null; then
    ok "VM 입니다 — $(cat /sys/class/dmi/id/product_name 2>/dev/null)"
else
    bad "가상 머신이 아닌 것 같습니다. 다크웹 쪽이 이 기기로 내려옵니다."
    say "그래도 계속하려면 10초 안에 아무 키나 누르십시오."
    if ! read -r -t 10 -n 1; then
        say "멈췄습니다."
        exit 1
    fi
fi

# ── 2. tor ─────────────────────────────────────────────────────────
step "2. tor"
if command -v tor >/dev/null 2>&1; then
    ok "이미 깔려 있습니다 — $(tor --version 2>/dev/null | head -1)"
else
    need_sudo || exit 1
    say "받습니다..."
    export DEBIAN_FRONTEND=noninteractive
    as_root apt-get update -qq || { bad "apt update 실패"; exit 1; }
    as_root apt-get install -y -qq tor || { bad "tor 설치 실패"; exit 1; }
    ok "깔았습니다 — $(tor --version 2>/dev/null | head -1)"
fi

# ── 3. torrc ───────────────────────────────────────────────────────
step "3. torrc 에 우리 규칙 넣기"
need_sudo || exit 1
if as_root grep -q "darkchoco" "$TORRC" 2>/dev/null; then
    ok "이미 들어 있습니다"
    as_root grep -q "HTTPTunnelPort ${PORT}" "$TORRC" 2>/dev/null \
        || say "다만 HTTPTunnelPort 가 ${PORT} 이 아닙니다. torrc 를 보십시오"
else
    as_root cp "$TORRC" "$TORRC.bak.$(date +%s)" 2>/dev/null || true
    as_root tee -a "$TORRC" >/dev/null <<EOF

# ── darkchoco ────────────────────────────────────────────────
# 표준 라이브러리가 SOCKS 를 못 타서 HTTP CONNECT 를 씁니다.
HTTPTunnelPort ${PORT}

# 한국 출구를 안 씁니다. Tor 에도 한국 출구가 있어서, 안 막으면
# 우리 IP 는 아니어도 한국 주소가 남습니다.
# StrictNodes 가 있어야 이 제외가 지켜집니다.
ExcludeExitNodes {kr}
StrictNodes 1
EOF
    ok "넣었습니다 (HTTPTunnelPort ${PORT} · ExcludeExitNodes {kr} · StrictNodes 1)"
fi

# ── 4. 띄우기 ──────────────────────────────────────────────────────
step "4. tor 띄우기"
if listening; then
    ok "이미 떠 있습니다"
else
    if command -v systemctl >/dev/null 2>&1 &&
       systemctl is-system-running >/dev/null 2>&1; then
        as_root systemctl enable tor >/dev/null 2>&1 || true
        as_root systemctl restart tor >/dev/null 2>&1 && say "systemd 로 띄웁니다"
        sleep 3
    fi
    if ! listening; then
        say "직접 띄웁니다 (systemd 가 없는 자리입니다)"
        as_root pkill -x tor 2>/dev/null || true
        sleep 1
        as_root sh -c "nohup tor -f ${TORRC} >${LOG} 2>&1 &"
    fi
    for _ in $(seq 1 30); do listening && break; sleep 1; done
    if listening; then
        ok "${PORT} 열렸습니다"
    else
        bad "${PORT} 가 안 열립니다. ${LOG} 를 보십시오"
        exit 1
    fi
fi

# ── 5. 길이 뚫리기를 기다립니다 ────────────────────────────────────
step "5. 길이 뚫리기를 기다립니다"
say "Tor 가 중계 목록을 받는 데 1~5분 걸립니다."
say "ExcludeExitNodes 때문에 쓸 수 있는 출구가 줄어 더 느립니다."
bootstrapped() {
    grep -q "Bootstrapped 100%" "$LOG" 2>/dev/null ||
    as_root grep -q "Bootstrapped 100%" /var/log/tor/log 2>/dev/null ||
    as_root grep -q "Bootstrapped 100%" /var/log/tor/notices.log 2>/dev/null
}
for i in $(seq 1 150); do
    bootstrapped && break
    if [ $((i % 15)) = 0 ]; then
        PCT="$(grep -o "Bootstrapped [0-9]*%" "$LOG" 2>/dev/null | tail -1)"
        say "${PCT:-여는 중} ... ($((i * 2))초)"
    fi
    sleep 2
done

# ── 6. 정말 나가지나 ───────────────────────────────────────────────
step "6. 실제로 나가 보기"
ANSWER="$(curl -sS --max-time 90 --proxy "http://127.0.0.1:${PORT}" \
          https://check.torproject.org/api/ip 2>&1)"
if printf '%s' "$ANSWER" | grep -q '"IsTor":true'; then
    EXIT_IP="$(printf '%s' "$ANSWER" | sed -n 's/.*"IP":"\([^"]*\)".*/\1/p')"
    ok "Tor 를 탑니다. 밖에 남는 주소는 ${EXIT_IP} 입니다"
else
    bad "Tor 로 안 나갑니다"
    say "$ANSWER"
    say "${LOG} 를 보십시오. 학교 망이 Tor 를 막을 수 있습니다."
    exit 1
fi

# ── 7. 파이썬 쪽 ───────────────────────────────────────────────────
step "7. 파이썬 부품"
cd "$HERE" || exit 1
if [ ! -d .venv ]; then
    if ! python3 -m venv .venv 2>/dev/null; then
        say "python3-venv 를 받습니다..."
        as_root apt-get install -y -qq python3-venv && python3 -m venv .venv
    fi
fi
if [ -f .venv/bin/activate ]; then
    # shellcheck disable=SC1091
    . .venv/bin/activate
    if pip install -q -e packages; then
        ok "부품을 깔았습니다"
    else
        bad "부품 설치 실패"
    fi
else
    bad ".venv 를 못 만들었습니다. python3 로 그냥 돌려도 됩니다"
fi

# ── 8. 환경 변수 ───────────────────────────────────────────────────
step "8. 환경 변수"
LINE="export TOR_SOCKS_PROXY=http://127.0.0.1:${PORT}"
if grep -qF "$LINE" ~/.bashrc 2>/dev/null; then
    ok "~/.bashrc 에 이미 있습니다"
else
    {
        printf '\n# darkchoco — Tor 를 거쳐 나갑니다\n'
        printf '%s\n' "$LINE"
        printf 'export PYTHONIOENCODING=utf-8\n'
    } >> ~/.bashrc
    ok "~/.bashrc 에 넣었습니다"
fi
export TOR_SOCKS_PROXY="http://127.0.0.1:${PORT}"
export PYTHONIOENCODING=utf-8

if [ -z "${NOTION_TOKEN:-}" ] && [ ! -f ~/.config/darkchoco/notion_token.txt ]; then
    bad "노션 토큰이 없습니다. 읽기만 되고 못 씁니다"
    say "둘 중 하나로 넣으십시오."
    say "  echo '토큰' > ~/.config/darkchoco/notion_token.txt"
    say "  또는 ~/.bashrc 에  export NOTION_TOKEN=..."
    say "**저장소에 넣지 마십시오.** 이 자리에만 둡니다."
else
    ok "노션 토큰이 있습니다"
fi

# ── 9. 점검 ────────────────────────────────────────────────────────
step "9. 점검"
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
$PY dc.py doctor --net 2>&1 | sed -n '/밖으로 나가는 길/,$p' | sed 's/^/  /'

step "다 됐습니다"
say "미리보기      $PY dc.py crawl --limit 3"
say "실제로 반영    $PY dc.py crawl --apply"
say "차례표에 걸기  crontab -e 에 아래 한 줄"
say "  */30 * * * * cd $HERE && $HERE/.venv/bin/python dc.py auto >> ~/darkchoco-auto.log 2>&1"
echo
