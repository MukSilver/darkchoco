// 저장소 스냅샷(src/data)을 Supabase guide 스키마에 처음 채웁니다. 지금은 darkchoco-data 배치가 cases 를 채우므로 조치·등급표·단계·창구를 새로 넣을 때만 씁니다.
// 사용: SUPABASE_URL=... SUPABASE_SERVICE_KEY=... node scripts/seed-db.mjs
import { readFile } from "node:fs/promises";
import { configured, upsert } from "./db.mjs";

if (!configured()) { console.error("SUPABASE_URL 과 SUPABASE_SERVICE_KEY 가 필요합니다."); process.exit(1); }
const read = async (n) => JSON.parse(await readFile(new URL(`../src/data/${n}.json`, import.meta.url), "utf8"));
const [cases, actions, weights, stages, desks] = await Promise.all(["cases", "actions", "weights", "stages", "desks"].map(read));

await upsert("weights", Object.entries(weights).map(([item, w]) => ({ item, acct: w.acct || 0, phish: w.phish || 0, ident: w.ident || 0, money: w.money || 0, priv: w.priv || 0 })), "item");
await upsert("stages", stages, "idx");
await upsert("desks", desks.map((d) => ({ name: d.name, url: d.url })), "name");
await upsert("actions", actions.map((a) => ({ id: a.id, risk: a.risk, urgency: a.urgency, title: a.title, why: a.why, effect: a.effect, limit_note: a.limit, undo_note: a.undo, cond: a.cond, free: a.free, desk: a.desk, url: a.url, minutes: a.minutes, prep: a.prep, steps: a.steps, alt: a.alt, go: a.go, need: a.need, basis: a.basis })), "id");
await upsert("cases", cases.map((c) => ({ id: c.id, industry: c.industry, title: c.title, gate: c.gate, spread: c.spread, freshness: c.freshness, stage_idx: c.stageIdx, confirmed: c.confirmed, claimed: c.claimed })), "id");
console.log(`채움: 사고 ${cases.length}, 조치 ${actions.length}, 등급표 ${Object.keys(weights).length}, 단계 ${stages.length}, 창구 ${desks.length}`);
