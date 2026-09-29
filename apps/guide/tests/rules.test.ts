import { describe, it, expect } from "vitest";
import { levels, pick, nextOf, stageOf, progress, ranked, josa } from "../src/lib/rules";
import { data } from "../src/lib/data";
import type { ItemId } from "../src/lib/types";

const { weights: W, actions, stages, when } = data;
const S = (...ids: ItemId[]) => new Set<ItemId>(ids);

describe("등급표", () => {
  it("주민등록번호 하나로 명의 도용과 금전 피해가 높음", () => {
    const L = levels(S("rrn"), W);
    expect(L.ident).toBe(3);
    expect(L.money).toBe(3);
    expect(L.acct).toBe(0);
  });
  it("이름과 전화번호가 함께 새면 사칭이 한 단계 오른다", () => {
    expect(levels(S("phone"), W).phish).toBe(2);
    expect(levels(S("name", "phone"), W).phish).toBe(3);
  });
  it("이름과 주민등록번호가 함께 새면 명의 도용은 높음", () => {
    expect(levels(S("name", "rrn"), W).ident).toBe(3);
  });
  it("기타만 고르면 등급이 하나도 없다", () => {
    expect(ranked(levels(S("etc"), W))).toEqual([]);
  });
});

describe("조치 고르기", () => {
  it("설계서 3.8 예시: 금융 사고 네 항목이면 15개가 뜨고 계정 조치는 없다", () => {
    const sel = S("name", "phone", "rrn", "finance");
    const L = levels(sel, W);
    const picked = pick(actions, sel, L, 1, stages);
    expect(picked.length).toBe(15);
    expect(picked.some(({ action }) => action.risk === "acct")).toBe(false);
    expect(nextOf(picked, new Set(), new Set())?.action.title).toBe("기관이나 회사를 사칭하는 전화와 문자에 응하지 않기");
    expect(progress(picked, new Set())).toEqual({ total: 17, finished: 2 });
  });
  it("항목 아홉을 다 고르면 22개가 모두 뜬다", () => {
    const sel = S("name", "phone", "email", "address", "account", "rrn", "finance", "internal", "etc");
    expect(pick(actions, sel, levels(sel, W), null, stages).length).toBe(22);
  });
  it("시급성이 먼저, 그 안에서는 단계별 위험 순서", () => {
    const sel = S("name", "phone", "rrn", "finance");
    const p = pick(actions, sel, levels(sel, W), 1, stages).map(({ action }) => action.urgency);
    const order = { now: 0, today: 1, watch: 2 };
    for (let i = 1; i < p.length; i++) expect(order[p[i]]).toBeGreaterThanOrEqual(order[p[i - 1]]);
  });
  it("완료하면 다음 할 일이 바뀌고, 미루면 뒤로 간다", () => {
    const sel = S("name", "phone", "rrn", "finance");
    const picked = pick(actions, sel, levels(sel, W), 1, stages);
    const first = picked[0].index;
    expect(nextOf(picked, new Set([first]), new Set())?.action.title).toBe("카드 사용 정지하고 재발급 신청하기");
    expect(nextOf(picked, new Set(), new Set([first]))?.index).not.toBe(first);
    const all = new Set(picked.map(({ index }) => index));
    expect(nextOf(picked, all, new Set())).toBeNull();
  });
});

describe("퍼진 단계", () => {
  it("사고가 있으면 그 단계, 없으면 받은 시점으로 추정", () => {
    expect(stageOf(2, null, when)).toEqual({ idx: 2, est: false });
    expect(stageOf(null, "m3", when)).toEqual({ idx: 1, est: true });
    expect(stageOf(null, "y1p", when)).toEqual({ idx: 2, est: true });
    expect(stageOf(null, "unk", when)).toEqual({ idx: null, est: true });
  });
});

describe("자료 검사", () => {
  it("조치 22개 모두 누를 곳이 하나 이상", () => {
    for (const a of actions) expect(!!a.url || a.go.length > 0, a.title).toBe(true);
  });
  it("조치의 필요 항목과 근거 항목은 항목표에 있는 값", () => {
    const ids = new Set(data.items.map((i) => i.id));
    for (const a of actions) for (const x of [...a.need, ...a.basis]) expect(ids.has(x), `${a.title}: ${x}`).toBe(true);
  });
  it("조사 붙이기", () => {
    expect(josa("이름", "이", "가")).toBe("이");
    expect(josa("전화번호", "이", "가")).toBe("가");
  });
});
