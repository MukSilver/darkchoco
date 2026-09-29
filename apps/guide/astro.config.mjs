// @ts-check
import { defineConfig } from "astro/config";
import preact from "@astrojs/preact";

// 설계서 5장: 정적 출력. 사고마다 페이지를 빌드 때 만듭니다. 서버 기능과 어댑터는 두지 않습니다.
export default defineConfig({
  site: process.env.SITE_URL || "https://guide.example.com",
  output: "static",
  trailingSlash: "always",
  build: { format: "directory", inlineStylesheets: "always" },
  integrations: [preact()],
  compressHTML: true,
});
