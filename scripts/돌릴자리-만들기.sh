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

# 비밀번호를 물을 때 어디서 받나. DARKCHOCO_SUDO_PW 가 있으면 sudo 가
# 그것을 쓰게 합니다. 창이 없는 자리(VM 을 밖에서 부릴 때)에서는 sudo 가
# 물어볼 데가 없어 그냥 멈춥니다.
#
# 도우미 파일은 이 스크립트가 끝나면 지웁니다.
if [ -n "${DARKCHOCO_SUDO_PW:-}" ] && [ "$(id -u)" != "0" ]; then
    ASKPASS="$(mktemp)"
    cat > "$ASKPASS" <<'ASKPASS_EOF'
#!/bin/sh
# sudo 가 비밀번호를 물을 때 부르는 도우미입니다. 환경 변수에서 읽습니다.
printf %s "$DARKCHOCO_SUDO_PW"
ASKPASS_EOF
    chmod 700 "$ASKPASS"
    export SUDO_ASKPASS="$ASKPASS"
    trap 'rm -f "$ASKPASS"' EXIT INT TERM
fi

as_root() {
    if [ "$(id -u)" = "0" ]; then
        "$@"
    elif [ -n "${SUDO_ASKPASS:-}" ]; then
        sudo -A "$@"
    else
        sudo "$@"
    fi
}

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
    if [ -n "${SUDO_ASKPASS:-}" ] && sudo -A true 2>/dev/null; then
        return 0
    fi
    bad "sudo 가 비밀번호를 묻습니다."
    say "창이 없는 자리라면 비밀번호를 넘겨 주십시오."
    say "    DARKCHOCO_SUDO_PW=... bash scripts/돌릴자리-만들기.sh"
    say "아니면 먼저 한 번 넣어 두고 다시 돌리십시오."
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
        bad "${PORT} 가 안 열립니다."
        # 왜인지 로그에서 뽑아 줍니다. 파일을 보라고만 하면 팀원이
        # 무엇을 찾아야 하는지 모릅니다.
        WHY="$(grep -hE "\[warn\]|\[err\]" "$LOG" /var/log/tor/log 2>/dev/null | tail -4)"
        [ -n "$WHY" ] && printf "     %s" "$WHY"; echo
        if printf '%s' "$WHY" | grep -q "Address already in use"; then
            say ""
            say "다른 tor 가 이미 그 포트를 쥐고 있습니다."
            say "  · WSL 은 배포판끼리 localhost 를 함께 씁니다. 다른"
            say "    배포판에서 tor 를 띄웠으면 여기서 부딪힙니다"
            say "  · 이미 도는 것을 그냥 써도 됩니다:"
            say "      export TOR_SOCKS_PROXY=http://127.0.0.1:9080"
            say "  · 따로 띄우려면 SocksPort 도 바꾸십시오:"
            say "      /etc/tor/torrc 에  SocksPort 9151"
        fi
        exit 1
    fi
fi

# ── 5. 길이 뚫리기를 기다립니다 ────────────────────────────────────
step "5. 길이 뚫리기를 기다립니다"
say "Tor 가 중계 목록을 받는 데 1~5분 걸립니다."
say "ExcludeExitNodes 때문에 쓸 수 있는 출구가 줄어 더 느립니다."
bootstrapped() {
    # 로그가 어디로 갈지는 자리마다 다릅니다. systemd 가 띄우면 journald 로
    # 갑니다. 파일만 보면 다 됐는데도 5분을 헛기다립니다.
    grep -q "Bootstrapped 100%" "$LOG" 2>/dev/null && return 0
    as_root grep -q "Bootstrapped 100%" /var/log/tor/log 2>/dev/null && return 0
    as_root grep -q "Bootstrapped 100%" /var/log/tor/notices.log 2>/dev/null && return 0
    if command -v journalctl >/dev/null 2>&1; then
        as_root journalctl -u tor@default -u tor --no-pager -n 200 2>/dev/null |
            grep -q "Bootstrapped 100%" && return 0
    fi
    # 로그를 못 찾아도 실제로 나가지면 다 된 것입니다. 이것이 진짜 검사입니다.
    curl -sS --max-time 12 --proxy "http://127.0.0.1:${PORT}"          https://check.torproject.org/api/ip 2>/dev/null | grep -q '"IsTor"' && return 0
    return 1
}

for i in $(seq 1 100); do
    bootstrapped && { ok "길이 뚫렸습니다"; break; }
    if [ $((i % 10)) = 0 ]; then
        PCT="$(grep -o "Bootstrapped [0-9]*%" "$LOG" 2>/dev/null | tail -1)"
        say "${PCT:-여는 중} ... ($((i * 3))초)"
    fi
    sleep 3
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

# **여기서 정합니다.** 7-2 가 $PY 를 쓰는데 예전에는 9단계에서 정하고
# 있었습니다. set -u 때문에 7-2 에서 셸이 통째로 끝나, 8단계 환경변수
# 안내와 9단계 점검이 아예 안 돌았습니다.
# .venv 는 바로 위 7단계에서 만들어지므로 이 자리가 가장 이릅니다.
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

# ── 7-2. 브라우저 ──────────────────────────────────────────────────
# 수집기 일곱 중 다섯이 Playwright page 를 받습니다. 없으면 첫 화면
# 글자만 보고 끝나서 채우는 칸이 절반으로 줍니다.
#
# 클라우드플레어 앞단도 브라우저라야 지납니다. 2026-08-30 실측으로
# 「연결이 안 됩니다」 461줄 중 상당수가 그것입니다.
#
# 크롬은 400MB 쯤 됩니다. 안 깔려도 크롤러는 돕니다 — 그때는 http 로만
# 열고 못 돈 수집기를 화면에 적습니다.
step "7-2. 브라우저 (Playwright)"
if [ "${DARKCHOCO_SKIP_BROWSER:-}" = "1" ]; then
    say "DARKCHOCO_SKIP_BROWSER=1 이라 건너뜁니다"
elif "$PY" -c "import playwright.sync_api" 2>/dev/null && [ -d ~/.cache/ms-playwright ]; then
    ok "playwright 와 크롬이 이미 있습니다"
else
    # **apt 의 playwright 를 쓰면 안 됩니다.**
    #
    # 칼리에 python3-playwright(1.55.0+ds)가 있는데 데비안이 드라이버를
    # 떼어 냅니다(+ds = Debian source). 그것으로 띄우면 이렇게 죽습니다.
    #
    #     Connection.init: Connection closed while reading from the driver
    #
    # pip 판은 node 와 드라이버를 안에 갖고 옵니다. .venv 안에 깝니다.
    say "playwright 를 받습니다 (크롬까지 400MB 쯤, 몇 분 걸립니다)..."
    if "$PY" -m pip install -q "playwright>=1.45,<2"; then
        # 크롬만 받습니다. --with-deps 는 root 가 필요한데, 칼리에는
        # 필요한 라이브러리가 대부분 이미 있습니다.
        if "$PY" -m playwright install chromium >/dev/null 2>&1; then
            ok "브라우저까지 깔았습니다"
        else
            say "시스템 라이브러리가 모자란 것 같습니다. 받아 봅니다..."
            as_root "$PY" -m playwright install --with-deps chromium >/dev/null 2>&1                 && ok "브라우저까지 깔았습니다"                 || bad "크롬을 못 깔았습니다. http 로만 열립니다 (수집기 5개가 안 돕니다)"
        fi
    else
        bad "playwright 를 못 깔았습니다. http 로만 열립니다"
    fi
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
$PY dc.py doctor --net 2>&1 | sed -n '/밖으로 나가는 길/,$p' | sed 's/^/  /'

step "다 됐습니다"
say "미리보기      $PY dc.py crawl --limit 3"
say "실제로 반영    $PY dc.py crawl --apply"
say "차례표에 걸기  crontab -e 에 아래 한 줄"
say "  */30 * * * * cd $HERE && $HERE/.venv/bin/python dc.py auto >> ~/darkchoco-auto.log 2>&1"
echo
