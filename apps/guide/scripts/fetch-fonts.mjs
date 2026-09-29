// Noto Sans KR 를 글자 범위별로 쪼갠 woff2 파일로 받아 public/fonts 에 두고, src/styles/fonts.css 를 만듭니다.
// 한 번 받아 두면 방문자는 외부 글꼴 서버에 접속하지 않습니다. 사용: node scripts/fetch-fonts.mjs
import { mkdir, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";

const CSS_URL = "https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36";

const css = await (await fetch(CSS_URL, { headers: { "User-Agent": UA } })).text();
await mkdir("public/fonts", { recursive: true });
const urls = [...css.matchAll(/url\((https:[^)]+\.woff2)\)/g)].map((m) => m[1]);
const names = new Map();
let n = 0;
for (const u of [...new Set(urls)]) {
  const buf = Buffer.from(await (await fetch(u)).arrayBuffer());
  const name = "nsk-" + createHash("sha1").update(u).digest("hex").slice(0, 10) + ".woff2";
  await writeFile("public/fonts/" + name, buf);
  names.set(u, "/fonts/" + name);
  n++;
}
const local = css.replace(/url\((https:[^)]+\.woff2)\)/g, (_, u) => `url(${names.get(u)})`);
await writeFile("src/styles/fonts.css", "/* Noto Sans KR, 직접 호스팅. scripts/fetch-fonts.mjs 가 만듭니다 */\n" + local);
console.log(`글꼴 파일 ${n}개, fonts.css 갱신`);
