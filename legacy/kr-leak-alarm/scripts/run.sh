#!/usr/bin/env bash
# Linux / macOS 실행 스크립트
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
  echo "[*] 가상환경을 생성합니다..."
  python3 -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip --quiet
  ./.venv/bin/python -m pip install -r requirements.txt --quiet
fi

[ -f config.json ] || cp config.example.json config.json

./.venv/bin/python -m collector.main run "$@"
echo
echo "[*] 완료. 대시보드: ./.venv/bin/python -m collector.main serve"
