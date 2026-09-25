/**
 * 사건 보고서 팝업 한 장 — 설계서 4.3.4 (L682-711), 피그마 ⑦-4 하단 · 사건 상세 모달.
 *
 * 화면(`EventReport.tsx`)과 「JSON 내보내기」가 **이 모형 하나를 같이 쓴다.** 설계서
 * L707 이 「JSON 내보내기: 팝업에 표시된 정보 그대로」라서, 모형에 없는 칸은 화면에도
 * 파일에도 없다. 칸을 더하려면 여기 더한다.
 *
 * 설계서 표와 다른 곳 — **피해 조직 이름은 지도 어디에도 안 낸다** (2026-09-26 결정)
 *
 *   피해 조직 줄       없다. 설계서 L690 표 · L696 「실명 표시」를 따르지 않는다
 *   제목              자료 제목 대신 분류 칸으로 지은 것 (`eventTitle`, 2026-09-25)
 *   설명              검증 요약 · 비고(사람이 쓴 글) 대신 분류 칸으로 지은 자동 문장
 *   출처              원문 URL · 캡처 · 받기 없이 소스 종류만. 굽기가 링크를 안 싣는다
 *   활동도 영향 줄     없다 (설계서 L697, 5.3 ⑦-5)
 */

import { EV_KIND_LABEL, EV_KIND_TONE, RISK_LABEL, RISK_TONE, dayOf, eventTitle, sizeText, utcStamp } from "./events.ts";
import { CONF_CHIP, CONF_LABEL, KIND_LABEL, KIND_ORDER, SIZE_LABEL, VERDICT_LABEL, confOfVerdict, josa } from "./relations.ts";
import type { Confidence, Ev, Relation } from "./types.ts";

/** 출처 절에 늘 붙는 안내. 원문을 싣지 않는다는 것을 숨기지 않고 적는다 */
export const SOURCE_NOTE = "원문 URL · 캡처는 공개 지도에 싣지 않습니다.";

export type ReportChip = {
  label: string;
  /** `RelBits` `Chip` 의 상태색 이름 */
  tone: string;
  /** 사건 번호 태그 — 고정폭 글씨 (피그마 컴포넌트 Tag) */
  tag?: boolean;
};

export type ReportField = {
  label: string;
  value: string;
  /** 누르면 팝업을 닫고 지도에서 이 영토를 고른다 (설계서 L704) */
  territoryId?: string;
  /** 유출 항목 칩. 있으면 `value` 대신 칩으로 그린다 */
  items?: string[];
};

export type ReportLinked = { id: string; title: string; place: string; conf: Confidence | null };

export type ReportRel = { id: string; route: string; kind: string; conf: Confidence };

export type EventReportModel = {
  id: string;
  /** 공식 발표 사고(유출 사고 DB) 변형 (설계서 L698) */
  official: boolean;
  title: string;
  /** 머리 둘째 줄 — 영토 · 섬 · 게시 시각 (UTC) */
  meta: string;
  chips: ReportChip[];
  fields: ReportField[];
  description: string;
  linked: ReportLinked[];
  relations: ReportRel[];
  source: { type: string; meta: string };
};

export type ReportNames = {
  /** 영토 이름. 기준일과 무관하게 명부에서 찾는다 — 검색 「상세」는 기준일 밖 사건도 연다 */
  nameOf: (territoryId: string) => string;
  /** 그 영토의 섬 이름 (`포럼` · `랜섬웨어` …) */
  islandOf: (territoryId: string) => string;
};

/** 규모 등급 낱말. 설명 문장 「규모 등급은 큼입니다」 에 쓴다 */
const GRADE_WORD: Record<Ev["size"], string | null> = {
  large: "큼",
  medium: "중간",
  small: "작음",
  unknown: null,
};

/**
 * 국가 부호 → 이름. 설명 문장에 「한국(KR)」 으로 쓴다.
 *
 * `tools/bake.py` 의 `COUNTRY_CODE` 를 거꾸로 옮긴 것이다. 굽기가 그 표 밖 부호를
 * 막으므로 여기 없는 부호는 없어야 하지만, 들어오면 부호만 쓴다
 */
const COUNTRY_NAME: Record<string, string> = {
  KR: "한국", US: "미국", JP: "일본", CN: "중국", TW: "대만",
  VN: "베트남", IN: "인도", RU: "러시아", GB: "영국", DE: "독일",
  FR: "프랑스", CA: "캐나다", AU: "호주", TH: "태국", ID: "인도네시아",
  TR: "터키", BR: "브라질",
};

/** `KR` → `한국(KR)`. 모르는 부호는 그대로 */
function countryText(code: string): string {
  const name = COUNTRY_NAME[code];
  return name ? `${name}(${code})` : code;
}

/**
 * 외부 확인 칩 색. 조직 · 규제기관이 스스로 밝힌 것만 success 로 두고 나머지(언론
 * 보도 · 연구자 발견 · 게시글만)는 neutral 이다. 시안에 이 칩이 없어 정한 값이다
 */
const CONFIRM_TONE: Record<string, string> = {
  "조직 공식 발표": "success",
  "규제기관 확정": "success",
};

/**
 * 연결된 사건 — 수집 DB 「같은 사건」 (설계서 L691 · L703). **양쪽 어느 줄에 적혀도
 * 잇는다** — 같은 사건은 방향이 없는 관계인데 노션에는 한쪽 줄에만 적힌 것이 있다.
 * 화면에 안 나오는 사건(반출 제외 · 허위)은 뺀다. 최신순이다.
 */
export function linkedOf(events: readonly Ev[], e: Ev): Ev[] {
  const mine = new Set(e.linked ?? []);
  return events
    .filter(
      (x) =>
        x.id !== e.id &&
        !x.excluded &&
        x.verdict !== "false" &&
        (mine.has(x.id) || (x.linked ?? []).includes(e.id)),
    )
    .sort(
      (a, b) => b.postedAt.slice(0, 16).localeCompare(a.postedAt.slice(0, 16)) || a.id.localeCompare(b.id),
    );
}

/**
 * 설명 — 분류 칸으로만 짓는 자동 문장 (설계서 L691 「사건 요약」의 대신).
 *
 * 재료는 사건 종류 · 국가 · 산업 분야 · 규모 · 판정(공식 발표는 외부 확인) · 영토 ·
 * 행위자 핸들뿐이다. 검증 요약 · 비고는 사람이 쓰는 글이라 반출하지 않는다.
 * 조사는 「입니다」 로 끝을 맺어 받침에 덜 기대게 했다 — 행위자 주어만 `josa` 를 쓴다
 */
export function eventSummary(e: Ev, names: ReportNames): string {
  const place = names.nameOf(e.territoryId);
  const parts: string[] = [];
  const official = e.kind === "official";

  if (official) {
    parts.push(`${place}에 유출 위치가 보도된 공식 발표 사고입니다.`);
  } else {
    const what = e.kind ? `${EV_KIND_LABEL[e.kind]} 사건` : "사건";
    if (e.actorTerritoryId && e.actorTerritoryId !== e.territoryId) {
      const a = names.nameOf(e.actorTerritoryId);
      parts.push(`${a}${josa(a, "이", "가")} ${place}에 올린 ${what}입니다.`);
    } else {
      parts.push(`${place}에 올라온 ${what}입니다.`);
    }
  }

  // 국가와 산업 분야를 제 이름으로 말한다. 전에는 「대상 분류는 KR · 유통입니다」라
  // 부호가 분류 이름처럼 읽혔다. 둘을 쉼표로 이어 받침에 기대는 조사를 안 쓴다
  const target = [
    e.country ? `대상 국가는 ${countryText(e.country)}` : null,
    e.industry ? `${e.country ? "" : "대상 "}산업 분야는 ${e.industry}` : null,
  ].filter((x): x is string => !!x);
  if (target.length) parts.push(`${target.join(", ")}입니다.`);

  const size = sizeText(e);
  const grade = GRADE_WORD[e.size];
  if (size) parts.push(`${official ? "유출" : "주장"} 규모는 ${size}입니다.`);
  else if (grade) parts.push(`규모 등급은 ${grade}입니다.`);
  else parts.push("규모는 확인되지 않았습니다.");

  if (official) {
    if (e.confirm) parts.push(`외부 확인은 「${e.confirm}」입니다.`);
  } else {
    parts.push(`검증 판정은 「${VERDICT_LABEL[e.verdict]}」입니다.`);
  }
  return parts.join(" ");
}

/**
 * 팝업 한 장을 짓는다.
 *
 *   linked   연결된 사건 (`linkedOf`)
 *   rels     이 사건이 근거인 관계 (`touchesEvent`). 기준일로 거르지 않는다 — 누르면
 *            관계 탭으로 가며 그 관계가 보이는 분기로 기준일을 옮긴다 (검색 관계 고르기와 같다)
 */
export function eventReport(
  e: Ev,
  names: ReportNames,
  linked: readonly Ev[],
  rels: readonly Relation[],
): EventReportModel {
  const place = names.nameOf(e.territoryId);
  const island = names.islandOf(e.territoryId);
  const official = e.kind === "official";
  const posted = utcStamp(e.postedAt);
  // 게시 시각이 없어 관측 시각 · 수집일을 넣은 사건은 그렇다고 적는다 (types.ts `dateSubstituted`)
  const postedText = e.dateSubstituted ? `${posted} (관측 · 수집일로 대신)` : posted;
  const size = sizeText(e) ?? SIZE_LABEL[e.size];
  const items = e.leakItems ?? [];
  const itemField: ReportField = items.length
    ? { label: "유출 항목", value: items.join(" · "), items: [...items] }
    : { label: "유출 항목", value: "기록 없음" };
  const idTag: ReportChip = { label: e.id, tone: "neutral", tag: true };

  let chips: ReportChip[];
  let fields: ReportField[];
  if (official) {
    // 설계서 L698 — 칩은 공식 발표와 외부 확인 값, 표는 사고 시점 · 공표 시점 · 유출 규모 · 유출 항목
    chips = [
      { label: EV_KIND_LABEL.official, tone: EV_KIND_TONE.official },
      ...(e.confirm ? [{ label: `외부 확인 · ${e.confirm}`, tone: CONFIRM_TONE[e.confirm] ?? "neutral" }] : []),
      idTag,
    ];
    fields = [
      { label: "사고 시점", value: e.occurredAt ?? "기록 없음" },
      { label: "공표 시점", value: postedText },
      { label: "유출 규모", value: size },
      itemField,
    ];
  } else {
    const conf = confOfVerdict(e.verdict);
    chips = [
      ...(e.kind ? [{ label: EV_KIND_LABEL[e.kind], tone: EV_KIND_TONE[e.kind] }] : []),
      ...(conf ? [{ label: CONF_LABEL[conf], tone: CONF_CHIP[conf] }] : []),
      ...(e.risk ? [{ label: `위험도 ${RISK_LABEL[e.risk]}`, tone: RISK_TONE[e.risk] }] : []),
      idTag,
    ];
    const actor = e.actorTerritoryId && e.actorTerritoryId !== e.territoryId ? e.actorTerritoryId : null;
    fields = [
      { label: "발생 일시", value: postedText },
      { label: "엔티티", value: `${place} (${island})`, territoryId: e.territoryId },
      // 「행위자 → 영토」 — 패널 [사건] 행 아랫줄과 같다 (page.tsx `whereOf`)
      { label: "게시 위치", value: actor ? `${names.nameOf(actor)} → ${place}` : place },
      { label: "유출 규모", value: size },
      itemField,
    ];
  }

  return {
    id: e.id,
    official,
    title: eventTitle(e),
    meta: `${place} · ${island} 섬 · ${posted}`,
    chips,
    fields,
    description: eventSummary(e, names),
    linked: linked.map((x) => ({
      id: x.id,
      title: eventTitle(x),
      place: names.nameOf(x.territoryId),
      conf: confOfVerdict(x.verdict),
    })),
    relations: [...rels]
      .sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind) || a.id.localeCompare(b.id))
      .map((r) => ({
        id: r.id,
        route: `${names.nameOf(r.from)} → ${names.nameOf(r.to)}`,
        kind: KIND_LABEL[r.kind],
        conf: r.confidence,
      })),
    source: official
      ? { type: `출처 종류 · ${e.sourceKind ?? "기록 없음"}`, meta: `공표 ${dayOf(e)}` }
      : { type: `수집 소스 · ${island} 섬`, meta: `게시 ${dayOf(e)} · 판정 ${VERDICT_LABEL[e.verdict]}` },
  };
}

/**
 * 「JSON 내보내기」 내용 (설계서 L707 「팝업에 표시된 정보 그대로」). 화면 글자를
 * 그대로 담는다 — 칩 색 같은 그리기 값만 뺀다. 내보낸 시각은 안 넣는다(화면에 없다)
 */
export function reportJson(m: EventReportModel) {
  return {
    id: m.id,
    title: m.title,
    meta: m.meta,
    chips: m.chips.map((c) => c.label),
    fields: m.fields.map((f) => ({ label: f.label, value: f.value })),
    description: m.description,
    linked: m.linked.map((x) => ({
      id: x.id,
      title: x.title,
      place: x.place,
      confidence: x.conf ? CONF_LABEL[x.conf] : null,
    })),
    relations: m.relations.map((r) => ({ id: r.id, route: r.route, kind: r.kind, confidence: CONF_LABEL[r.conf] })),
    source: { ...m.source, note: SOURCE_NOTE },
  };
}
