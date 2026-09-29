// 조치에 걸린 기관 주소가 열리는지 실제 브라우저로 확인합니다. 죽은 주소가 있으면 디스코드로 알립니다.
// 사이트가 죽어 있으면 주소가 틀린 것이 아니라 기관 서버 문제인 경우가 많으니, 주소를 고치기 전에 며칠 뒤 다시 확인합니다.
import { readFile } from "node:fs/promises";
import { chromium } from "@playwright/test";
import { notify } from "./db.mjs";

const actions = JSON.parse(await readFile(new URL("../src/data/actions.json", import.meta.url), "utf8"));
const urls = new Map();
for (const a of actions) {
  if (a.url && !a.url.startsWith("tel:")) urls.set(a.url, a.desk || a.title);
  for (const g of a.go || []) if (!g.url.startsWith("tel:")) urls.set(g.url, g.label);
}
const browser = await chromium.launch();
const page = await browser.newPage({ userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36" });
const dead = [];
for (const [u, name] of urls) {
  try {
    const r = await page.goto(u, { waitUntil: "domcontentloaded", timeout: 45000 });
    const code = r ? r.status() : 0;
    console.log(`${code}  ${name}  ${u}`);
    if (code !== 200) dead.push(`${name} (${code}) ${u}`);
  } catch (e) { console.log(`실패  ${name}  ${u}  ${e.constructor.name}`); dead.push(`${name} (안 열림) ${u}`); }
}
await browser.close();
if (dead.length) { await notify(`가이드라인 링크 점검: ${urls.size}개 중 ${dead.length}개가 안 열립니다.\n` + dead.join("\n") + "\n기관 서버 문제일 수 있으니 며칠 뒤 다시 확인하세요."); process.exit(1); }
console.log(`주소 ${urls.size}개 모두 열립니다.`);
