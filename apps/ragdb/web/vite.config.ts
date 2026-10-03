import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 화면 (설계서 「개발 스택」: React + Vite + TS + Tailwind). 개발 중에는 /api 를 질의 서버(127.0.0.1:8787)로,
// /data 를 배치가 구운 스냅샷 폴더로 넘긴다. 배포는 Cloudflare 정적 호스팅이고 API 는 rag-api.도메인이다.
// 색 안. 기본은 B안(lightblack). VITE_THEME=blue 는 남색 A안, black 은 C안(검정 바탕 + 회색 옆 창) (src/index.css 의 [data-theme])
const theme = process.env.VITE_THEME || 'lightblack'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    { name: 'ragdb-theme', transformIndexHtml: (html) => html.replace('<html lang="ko">', `<html lang="ko" data-theme="${theme}">`) },
  ],
  // 작은 글꼴 조각을 CSS 안에 박지 않고 파일로 둔다. 박으면 응답 머리말의 font-src 'self' 에 막힌다 (public/_headers)
  build: { assetsInlineLimit: 0 },
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8787', changeOrigin: true },
      // 스냅샷 폴더(data/snapshot)를 8788 에 그대로 띄운다: python -m http.server 8788 --directory data/snapshot
      '/data': { target: 'http://127.0.0.1:8788', changeOrigin: true, rewrite: (p) => p.replace(/^\/data/, '') },
    },
  },
})
