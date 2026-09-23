import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cloudflare 에 정적 파일로 올린다 (wrangler.jsonc). 서버가 도는 곳이 없다.
  // 화면은 구운 파일(src/data/map.json)만 읽고 노션 · Supabase 를 부르지 않는다
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
