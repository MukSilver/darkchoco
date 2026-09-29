// 구워 오는 파일(src/data/cases.json, flow.json)은 저장소에 없습니다. 새 클론에서도 dev, build, test 가 돌도록 빈 파일을 만듭니다.
// 있는 파일은 건드리지 않습니다.
//   node scripts/ensure-data.mjs           없으면 빈 파일을 만듦
//   node scripts/ensure-data.mjs --baked   배포 전 확인. 사고가 0건이면 멈춤 (빈 목록으로 실제 사이트를 덮지 않으려는 것)
import { readFile, writeFile } from "node:fs/promises";

const OUT = new URL("../src/data/", import.meta.url);
const EMPTY = { cases: [], flow: [["1년 이내 사고", [0, 0, 0]], ["1년 이상 된 사고", [0, 0, 0]]] };

const read = async (name) => { try { return JSON.parse(await readFile(new URL(name + ".json", OUT), "utf8")); } catch { return null; } };

for (const [name, empty] of Object.entries(EMPTY)) {
  if ((await read(name)) === null) {
    await writeFile(new URL(name + ".json", OUT), JSON.stringify(empty, null, 1) + "\n");
    console.log(`${name}.json 이 없어 빈 파일을 만들었습니다. 실제 사고를 보려면 SUPABASE_URL 과 SUPABASE_ANON_KEY 를 넣고 npm run fetch-db 를 돌립니다.`);
  }
}

if (process.argv.includes("--baked")) {
  const cases = await read("cases");
  if (!Array.isArray(cases) || cases.length === 0) {
    console.error("사고가 0건입니다. 빈 목록으로 배포하지 않습니다. fetch-db 가 돌았는지, 비밀값이 들어 있는지 확인하십시오.");
    process.exit(1);
  }
  console.log(`구운 파일 확인: 사고 ${cases.length}건`);
}
