# apps/ragdb/web: 화면

묻고 답하기와 출처 원문 (설계서 「화면 정의」). React + Vite + TypeScript + Tailwind.
디자인 정본은 피그마 파일 「화면」 페이지이고 색은 `src/index.css` 의 값이 피그마 변수와 같다.

```
npm ci
npm run dev        개발 서버 (5173). /api 는 127.0.0.1:8787, /data 는 127.0.0.1:8788 로 넘긴다
npm run build      dist/ 에 굽는다
```

개발할 때 같이 띄울 것 (apps/ragdb 에서)

```
.venv\Scripts\python -m uvicorn server.main:app --host 127.0.0.1 --port 8787 --workers 1
python -m http.server 8788 --bind 127.0.0.1 --directory data/snapshot
```

설정 값은 `.env.example` 을 본다. 전부 공개 값이다. 비밀 열쇠는 여기 두지 않는다.
