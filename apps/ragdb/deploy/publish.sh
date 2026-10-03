#!/usr/bin/env bash
# 화면과 스냅샷을 Cloudflare 에 올린다 (설계서 「자료 준비」 6 올리기, 「개발 스택」: wrangler, Workers 정적 자산).
#
#   deploy/publish.sh            지난번에 올린 판과 지금 판이 다를 때만 올린다
#   deploy/publish.sh --force    판이 같아도 올린다 (화면 코드만 바뀌었을 때)
#   THEME=blue deploy/publish.sh --force    남색 A안으로 구워 다른 주소(ragdb-web-blue)에 올린다. 색 안을 견주어 볼 때 쓴다
#   THEME=navy deploy/publish.sh --force    C안(남색 바탕 + 회청 옆 창) → ragdb-web-navy
#
# 올리는 것: web/dist (화면) 와 그 안의 data/ (스냅샷: current.json, 지금 판 폴더).
# 스냅샷은 snapshot.py 의 반출 관문을 통과한 것만 data/snapshot 에 있다. 여기서는 관문을 다시 보고 통과할 때만 올린다.
# 열쇠는 .env 의 CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID. 화면 설정 값은 web/.env.production.local (공개 값).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY=".venv/bin/python"
[ -x "$PY" ] || PY=".venv/Scripts/python.exe"          # 윈도우에서 손으로 돌릴 때

SNAP="data/snapshot"
[ -f "$SNAP/current.json" ] || { echo "스냅샷이 없다 ($SNAP/current.json). refresh.py 를 먼저 돌린다"; exit 1; }
VERSION="$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['version'])" "$SNAP/current.json")"
# 색 안. 비우면 기본(B안, ragdb-web). 값을 주면 그 색으로 구워 ragdb-web-{값} 에 올리고, 올린 판도 따로 적는다
THEME="${THEME:-}"
LAST_FILE="data/published_version${THEME:+_$THEME}.txt"
LAST="$(cat "$LAST_FILE" 2>/dev/null || true)"

if [ "${1:-}" != "--force" ] && [ "$VERSION" = "$LAST" ]; then
  echo "올린 판($LAST)과 지금 판이 같다. 올리지 않는다"
  exit 0
fi

# 반출 관문을 한 번 더 본다. 걸리면 올리지 않는다 (걸린 값은 찍히지 않는다)
"$PY" scripts/snapshot.py --check

# 열쇠를 읽는다. 값은 찍지 않는다
set -a
# shellcheck disable=SC1091
. <(grep -E '^(CLOUDFLARE_API_TOKEN|CLOUDFLARE_ACCOUNT_ID)=' .env || true)
set +a
# 토큰이 없으면 wrangler 로그인(`npx wrangler login`)으로 올린다. 서버의 주간 예약은 로그인할 수 없으므로 토큰이 있어야 한다
[ -n "${CLOUDFLARE_API_TOKEN:-}" ] || echo ".env 에 CLOUDFLARE_API_TOKEN 이 없다. wrangler 로그인으로 올린다"

cd web
[ -d node_modules ] || npm ci
VITE_THEME="$THEME" npm run build
rm -rf dist/data
mkdir -p dist/data
cp "../$SNAP/current.json" dist/data/
cp -r "../$SNAP/$VERSION" "dist/data/$VERSION"
npx wrangler deploy ${THEME:+--name "ragdb-web-$THEME"}
cd ..

echo "$VERSION" > "$LAST_FILE"
echo "올렸다: 판 $VERSION${THEME:+ (색 안 $THEME)}"
