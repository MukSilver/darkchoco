// 빌드 직전에 가이드 DB를 한 번 읽어 src/data/*.json 스냅샷을 갱신합니다.
// 환경 변수가 없으면 있는 파일을 그대로 씁니다. 고정 내용(조치, 창구, 등급표)은 저장소에 있고,
// 사고 목록(cases.json)과 칸 그림(flow.json)은 저장소에 없어 ensure-data.mjs 가 만든 빈 파일로 빌드됩니다.
import { readFile, writeFile } from "node:fs/promises";
import { configured, select } from "./db.mjs";

const OUT = new URL("../src/data/", import.meta.url);
const write = (name, rows) => writeFile(new URL(name + ".json", OUT), JSON.stringify(rows, null, 1) + "\n");

if (!configured()) { console.log("SUPABASE_URL 이 없어 있는 파일을 그대로 씁니다."); process.exit(0); }

const [cases, actions, weights, stages, desks] = await Promise.all([
  select("cases", "select=*&order=id"), select("actions", "select=*&order=id"),
  select("weights", "select=*"), select("stages", "select=*&order=idx"), select("desks", "select=*&order=name"),
]);

// 검사: 줄 수가 20% 넘게 줄면 스냅샷을 바꾸지 않습니다 (설계서 5.3)
const prev = JSON.parse(await readFile(new URL("cases.json", OUT), "utf8"));
if (!process.env.FORCE && prev.length && cases.length < prev.length * 0.8) {
  console.error(`사고 수가 ${prev.length}에서 ${cases.length}로 줄었습니다. 스냅샷을 바꾸지 않습니다.`);
  process.exit(1);
}
const itemIds = new Set(JSON.parse(await readFile(new URL("items.json", OUT), "utf8")).map((i) => i.id));
for (const c of cases) for (const x of [...c.confirmed, ...c.claimed]) if (!itemIds.has(x)) { console.error(`사고 ${c.id}에 모르는 항목 ${x}`); process.exit(1); }
for (const a of actions) if (!a.url && !(a.go && a.go.length)) { console.error(`조치 ${a.id} (${a.title})에 누를 곳이 없습니다`); process.exit(1); }

await write("cases", cases.map((c) => ({ id: c.id, industry: c.industry, title: c.title, gate: c.gate, spread: c.spread, freshness: c.freshness, stageIdx: c.stage_idx, confirmed: c.confirmed, claimed: c.claimed.filter((x) => !c.confirmed.includes(x)) })));
await write("actions", actions.map((a) => ({ id: a.id, risk: a.risk, urgency: a.urgency, title: a.title, why: a.why, effect: a.effect, limit: a.limit_note, undo: a.undo_note, cond: a.cond, free: a.free, desk: a.desk, url: a.url, minutes: a.minutes, prep: a.prep, steps: a.steps, alt: a.alt, go: a.go, need: a.need, basis: a.basis })));
await write("weights", Object.fromEntries(weights.map((w) => [w.item, Object.fromEntries(["acct", "phish", "ident", "money", "priv"].filter((k) => w[k]).map((k) => [k, w[k]]))])));
await write("stages", stages.map((s) => ({ idx: s.idx, name: s.name, sub: s.sub, icon: s.icon, who: s.who, risk: s.risk, dots: s.dots, mix: s.mix, priority: s.priority })));
await write("desks", desks.map((d) => ({ name: d.name, url: d.url })));
let flow = [["1년 이내 사고", [0, 0, 0]], ["1년 이상 된 사고", [0, 0, 0]]];
try { const st = await select("stats", "select=key,value&key=eq.flow"); if (st[0]) flow = st[0].value; } catch { /* stats 표가 아직 없으면 빈 그림 */ }
await write("flow", flow);
console.log(`스냅샷 갱신: 사고 ${cases.length}, 조치 ${actions.length}, 창구 ${desks.length}`);
