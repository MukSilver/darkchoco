import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 화면 (설계서 「개발 스택」: React + Vite + TS + Tailwind). 개발 중에는 /api 를 질의 서버(127.0.0.1:8787)로,
// /data 를 배치가 구운 스냅샷 폴더로 넘긴다. 배포는 Cloudflare 정적 호스팅이고 API 는 rag-api.도메인이다.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8787', changeOrigin: true },
      '/data': { target: 'http://127.0.0.1:8788', changeOrigin: true },
    },
  },
})
