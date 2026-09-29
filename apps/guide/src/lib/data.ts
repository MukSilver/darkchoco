// 빌드 때 읽는 자료. src/data/*.json 은 가이드 DB(Supabase)에서 내려받은 스냅샷입니다.
// scripts/fetch-db.mjs 가 환경 변수가 있을 때 갱신하고, 없으면 있는 파일을 그대로 씁니다.
// cases.json 과 flow.json 은 저장소에 없습니다. 없으면 scripts/ensure-data.mjs 가 빈 파일을 만듭니다.
import items from "../data/items.json";
import risks from "../data/risks.json";
import groups from "../data/groups.json";
import weights from "../data/weights.json";
import levelTip from "../data/levelTip.json";
import stages from "../data/stages.json";
import when from "../data/when.json";
import gate from "../data/gate.json";
import spreadTip from "../data/spreadTip.json";
import actions from "../data/actions.json";
import cases from "../data/cases.json";
import desks from "../data/desks.json";
import calEvents from "../data/calEvents.json";
import flowJson from "../data/flow.json";
import type { Action, Case, Group, Item, Risk, Stage, Weights, When } from "./types";

export const data = {
  items: items as Item[],
  risks: risks as Risk[],
  groups: groups as Group[],
  weights: weights as Weights,
  levelTip: levelTip as Record<string, string>,
  stages: stages as Stage[],
  when: when as When[],
  gate: gate as unknown as Record<string, [string, string, string]>,
  spreadTip: spreadTip as Record<string, string>,
  actions: actions as Action[],
  cases: cases as Case[],
  desks: desks as { name: string; url: string | null }[],
  calEvents: calEvents as { days: number; label: string; title: string }[],
};

export const LABEL: Record<string, string> = Object.fromEntries(data.items.map((i) => [i.id, i.label]));
export const RNAME: Record<string, string> = Object.fromEntries(data.risks.map((r) => [r.id, r.label]));
export const RICON: Record<string, string> = Object.fromEntries(data.risks.map((r) => [r.id, r.icon]));
export const GROUP: Record<string, Group> = Object.fromEntries(data.groups.map((g) => [g.id, g]));

/** 「이렇게 흘러갔어요」 칸 그림. 검증이 끝난 사고 전체(허위 제외)를 개수만 센 것. 들여오기가 stats 표에 넣고 fetch-db 가 flow.json 으로 내림 */
export const flow = flowJson as [string, number[]][];
export const showFlow = flow.some(([, ns]) => ns.some((n) => n > 0));

/** 목록과 페이지에 쓰는 공개 제목. 회사 이름을 쓰지 않습니다 */
export const caseTitle = (c: Case) => c.title;
