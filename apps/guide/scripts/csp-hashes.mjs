// 빌드 결과의 인라인 스크립트 해시를 계산해 dist/_headers 의 CSP 에 넣습니다.
// 'unsafe-inline' 없이도 Astro 섬이 돌게 하기 위해서입니다. npm run build 끝에 자동으로 돕니다.
import { readFile, writeFile, readdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import { join } from "node:path";

async function htmlFiles(dir) {
  const out = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...(await htmlFiles(p)));
    else if (e.name.endsWith(".html")) out.push(p);
  }
  return out;
}

const hashes = new Set();
for (const f of await htmlFiles("dist")) {
  const html = await readFile(f, "utf8");
  for (const m of html.matchAll(/<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/gi)) {
    hashes.add("'sha256-" + createHash("sha256").update(m[1]).digest("base64") + "'");
  }
}
const tpl = await readFile("public/_headers", "utf8");
const out = tpl.replace("{{SCRIPT_HASHES}}", [...hashes].join(" "));
await writeFile("dist/_headers", out);
console.log(`CSP 인라인 스크립트 해시 ${hashes.size}개를 dist/_headers 에 넣었습니다.`);
