// 이 기기 브라우저에만 저장합니다. 개인정보는 없고, 항목 종류와 체크만 있습니다. 서버로 보내지 않습니다.
import type { ItemId, Plan } from "./types";

const PLAN_KEY = "guide-plan-v5";

export const store = {
  get(k: string): string | null { try { return localStorage.getItem(k); } catch { return null; } },
  set(k: string, v: string) { try { localStorage.setItem(k, v); } catch { /* 사생활 보호 모드 등 */ } },
  del(k: string) { try { localStorage.removeItem(k); } catch { /* 무시 */ } },
};

export function loadPlan(): Plan | null {
  try {
    const p = JSON.parse(store.get(PLAN_KEY) || "null");
    return p && p.src ? (p as Plan) : null;
  } catch { return null; }
}

export function savePlan(p: Omit<Plan, "t">) {
  store.set(PLAN_KEY, JSON.stringify({ ...p, t: Date.now() }));
}

export function forgetPlan() { store.del(PLAN_KEY); }

/** 안내문 경로에서 고른 값. 페이지를 넘어갈 때 브라우저 저장으로 넘깁니다.
 *  suspect 는 1단계에서 「의심스러워요」를 눌렀는지, keepDone 은 대응 한 장을 본 뒤라 완료 표시를 이어 갈지입니다 */
export interface Draft { sel: ItemId[]; when: string | null; ntype: string | null; suspect?: boolean; keepDone?: boolean }
const DRAFT_KEY = "guide-draft-v5";
export const emptyDraft = (): Draft => ({ sel: [], when: null, ntype: null, suspect: false, keepDone: false });
export function loadDraft(): Draft { try { return JSON.parse(store.get(DRAFT_KEY) || "null") || emptyDraft(); } catch { return emptyDraft(); } }
export function saveDraft(d: Draft) { store.set(DRAFT_KEY, JSON.stringify(d)); }
export function clearDraft() { store.del(DRAFT_KEY); }
export const isBlankDraft = (d: Draft) => !d.sel.length && !d.when && !d.ntype;

/** 안내문 경로 밖에서 안내문으로 들어오면 고른 값을 새로 시작합니다 (프로토타입의 route 와 같음).
 *  밖에서 오는 링크를 누를 때 표시를 남기고, 안내문 페이지가 열릴 때 그 표시를 보고 지웁니다.
 *  뒤로 가기와 새로고침에는 표시가 없어 그대로 이어집니다 */
const FLOW_KEY = "guide-flow-reset";
export function markFlowReset() { try { sessionStorage.setItem(FLOW_KEY, "1"); } catch { /* 무시 */ } }
export function takeFlowReset(): boolean { try { const v = sessionStorage.getItem(FLOW_KEY) === "1"; sessionStorage.removeItem(FLOW_KEY); return v; } catch { return false; } }

/** 보기 설정 */
export type Theme = "auto" | "light" | "dark";
export const prefs = {
  get big() { return store.get("guide-big") === "1"; },
  set big(v: boolean) { store.set("guide-big", v ? "1" : "0"); },
  get easy() { return store.get("guide-easy") === "1"; },
  set easy(v: boolean) { store.set("guide-easy", v ? "1" : "0"); },
  get theme(): Theme { return (store.get("guide-theme") as Theme) || "auto"; },
  set theme(v: Theme) { store.set("guide-theme", v); },
};

/** 설정이 바뀌면 화면 섬들이 다시 그리도록 알립니다 */
export function announcePrefs() { document.dispatchEvent(new CustomEvent("guide:prefs")); }
