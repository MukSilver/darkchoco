// Supabase 의 guide 스키마를 읽는 얇은 도우미. 브라우저에서는 절대 쓰지 않습니다.
// 사고와 통계는 darkchoco-data 배치가 채우므로 이 저장소는 읽기만 합니다. 쓰기는 seed-db.mjs(처음 한 번, 서비스 키)뿐입니다.
export const SUPABASE_URL = process.env.SUPABASE_URL;
export const SUPABASE_KEY = process.env.SUPABASE_ANON_KEY || process.env.SUPABASE_SERVICE_KEY;
const SCHEMA = "guide";

export function configured() { return !!(SUPABASE_URL && SUPABASE_KEY); }

function headers(extra = {}) {
  return { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, "Content-Type": "application/json", "Accept-Profile": SCHEMA, "Content-Profile": SCHEMA, ...extra };
}

export async function select(table, query = "select=*") {
  const r = await fetch(`${SUPABASE_URL}/rest/v1/${table}?${query}`, { headers: headers() });
  if (!r.ok) throw new Error(`${table} 읽기 실패 ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function upsert(table, rows, onConflict) {
  if (!rows.length) return;
  const r = await fetch(`${SUPABASE_URL}/rest/v1/${table}?on_conflict=${onConflict}`, {
    method: "POST", headers: headers({ Prefer: "resolution=merge-duplicates,return=minimal" }), body: JSON.stringify(rows),
  });
  if (!r.ok) throw new Error(`${table} 쓰기 실패 ${r.status}: ${await r.text()}`);
}
