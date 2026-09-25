/**
 * 구운 지도 파일(`src/data/map.json`)이 있는지 본다.
 *
 * **map.json 은 저장소에 안 넣는다** (2026-09-25 최현서). 루트 `.gitignore` 의
 * `data/` 규칙에 걸려 있고, 공개 저장소의 git 기록에 한 번 들어가면 못 지운다.
 * 그래서 새 클론에는 이 파일이 없고, `mapData.ts` 가 정적으로 불러오므로
 * 없으면 빌드가 멈춘다.
 *
 *     node tools/ensure_map.mjs            없으면 빈 파일을 만든다. 화면이 예시 데이터로 물러선다
 *     node tools/ensure_map.mjs --baked    구운 파일이 아니면 멈춘다. 배포 전에 쓴다
 *
 * **배포는 빈 파일로 물러서지 않는다.** 물러서면 예시 데이터가 실제 사이트에 올라간다.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "data", "map.json");

// 굽기가 쓰는 칸 그대로 둔다. 사건이 0건이면 `isBaked` 가 거짓이 된다
const EMPTY = { generatedAt: null, territories: [], events: [], relations: [], links: [] };

function eventCount() {
  try {
    const data = JSON.parse(readFileSync(OUT, "utf-8"));
    return Array.isArray(data.events) ? data.events.length : 0;
  } catch {
    return 0;
  }
}

if (process.argv.includes("--baked")) {
  if (!existsSync(OUT) || eventCount() === 0) {
    console.error("구운 지도가 없습니다. 배포 전에 npm run bake 로 구우세요 (README 「굽기」)");
    process.exit(1);
  }
} else if (!existsSync(OUT)) {
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(EMPTY, null, 2) + "\n", "utf-8");
  console.log("구운 지도가 없어 빈 파일을 만들었습니다. 화면은 예시 데이터로 뜹니다");
}
