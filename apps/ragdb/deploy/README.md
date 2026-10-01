# 서버에 올리기

설계서 「개발 스택」 대로 올린다. 서버 하나에 질의 서버와 주간 배치를 두고, 화면과 스냅샷은 Cloudflare 에 둔다.

```
방문자 → Cloudflare (화면, 스냅샷, 사람 확인, 터널) → 서버 (질의 서버 127.0.0.1:8787, 주간 배치)
```

서버는 Ubuntu, 메모리 1GB 를 기준으로 썼다. 질의 서버가 600MB 쯤 쓰므로 예비 메모리(스왑) 2GB 를 잡는다.
열쇠는 `.env` 에만 둔다. 채팅, 저장소, 로그에 적지 않는다.

## 순서

### 1. 서버 준비 (한 번)

```bash
sudo bash setup.sh
```

스왑, 꾸러미(파이썬, node 22), `ragdb` 사용자, 저장소(`/opt/darkchoco`), 가상환경, 질의 서버 자동 실행 등록까지 한다.
저장소를 받기 전이라면 이 파일 하나만 서버에 올려 돌린다.

### 2. 열쇠 넣기

`.env.example` 을 보고 `/opt/darkchoco/apps/ragdb/.env` 를 만든다.

```bash
sudo install -o ragdb -g ragdb -m 600 /dev/null /opt/darkchoco/apps/ragdb/.env
sudoedit /opt/darkchoco/apps/ragdb/.env
```

질의 서버에 더 필요한 값

| 값 | 무엇 |
|---|---|
| `TURNSTILE_SECRET` | 사람 확인 비밀 열쇠. 비우면 사람 확인 없이 받는다 (공개할 때는 반드시 채운다) |
| `ALLOWED_ORIGINS` | 화면 주소. 예 `https://ragdb-web.계정.workers.dev` |
| `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | 화면과 스냅샷을 올릴 때 |

### 3. 판 만들기

```bash
sudo -u ragdb -H bash -c 'cd /opt/darkchoco/apps/ragdb && .venv/bin/python scripts/check_keys.py && .venv/bin/python scripts/refresh.py'
```

조직 이름 찾기가 바뀐 문서를 읽으므로 돈이 든다. 찾은 결과는 Supabase 에 있어서 다른 기계에서 이미 본 문서는 다시 읽지 않는다.

### 4. 질의 서버 띄우기

```bash
sudo systemctl start ragdb-api
curl -s http://127.0.0.1:8787/api/status
```

`"ok":true` 와 판 이름이 나오면 된다. 기록은 `journalctl -u ragdb-api -n 50`.

### 5. 터널

서버에 열린 포트를 두지 않는다. cloudflared 가 밖에서 들어오는 길을 만든다.

- 도메인이 있을 때 (설계서의 방식): Cloudflare 대시보드의 Zero Trust, Networks, Tunnels 에서 터널을 만들고 공개 주소 `rag-api.도메인` 을 `http://127.0.0.1:8787` 로 잇는다. 대시보드가 주는 설치 명령을 서버에서 돌리면 서비스로 등록된다.
- 도메인이 없을 때 (임시): `cloudflared tunnel --url http://127.0.0.1:8787` 이 임시 주소를 준다. 다시 띄울 때마다 주소가 바뀌고, 설계서는 답이 흘러오다 끊긴다는 이유로 쓰지 않기로 했다(CR-07). 개발 확인에만 쓰고 공개에는 쓰지 않는다.

터널 주소가 정해지면 화면 쪽 `VITE_API_BASE` 와 서버 쪽 `ALLOWED_ORIGINS` 를 맞춘다.

### 6. 화면과 스냅샷 올리기

화면 설정을 `web/.env.production.local` 에 적는다 (`web/.env.example` 참고. 전부 공개 값).

```bash
sudo -u ragdb -H bash -c 'cd /opt/darkchoco/apps/ragdb && deploy/publish.sh'
```

반출 관문을 다시 본 뒤 화면을 굽고, 스냅샷을 `dist/data/` 에 넣어 `npx wrangler deploy` 로 올린다. 올린 판은 `data/published_version.txt` 에 적는다.
화면 코드만 바뀌었으면 `deploy/publish.sh --force`.

### 7. 주간 예약

```bash
sudo crontab -u ragdb /opt/darkchoco/apps/ragdb/deploy/crontab
```

월요일 04시(한국 시간)에 `refresh.py` 를 돌리고, 새 판이 생겼으면 올린다.

### 8. 감시

```bash
cd apps/ragdb/monitor
npx wrangler secret put DISCORD_WEBHOOK
npx wrangler deploy
```

`wrangler.jsonc` 의 `STATUS_URL` 에 질의 서버의 상태 주소를 적는다. 5분마다 보고, 멈추면 디스코드로 알린다.

## 코드를 새로 받을 때

```bash
sudo -u ragdb -H bash -c 'cd /opt/darkchoco && git pull --ff-only && cd apps/ragdb && .venv/bin/python -m pip install -r requirements.txt'
sudo systemctl restart ragdb-api
sudo -u ragdb -H bash -c 'cd /opt/darkchoco/apps/ragdb && deploy/publish.sh --force'
```

## 되돌리기

판은 폴더 하나로 닫혀 있고 직전 판을 남겨 둔다. `data/current.txt` 한 줄을 직전 판 이름으로 바꾸면 질의 서버는 다음 질문부터 그 판을 쓴다.
스냅샷은 `data/snapshot/current.json` 을 같이 바꾸고 `deploy/publish.sh --force`.

## 도메인이 생기면 바꿀 것

| 자리 | 값 |
|---|---|
| Cloudflare | 화면에 `rag.도메인`, 터널에 `rag-api.도메인` 을 붙인다 (같은 계정에 도메인이 있어야 한다) |
| `web/.env.production.local` | `VITE_API_BASE=https://rag-api.도메인` |
| 서버 `.env` | `ALLOWED_ORIGINS=https://rag.도메인` |
| `web/public/_headers` | `connect-src` 를 `'self' https://rag-api.도메인` 으로 좁힌다 |
| Turnstile | 위젯의 도메인 목록에 `rag.도메인` 추가 |
| `monitor/wrangler.jsonc` | `STATUS_URL=https://rag-api.도메인/api/status` |
