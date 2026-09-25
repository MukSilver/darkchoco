/**
 * 검색 결과 한 줄 — 검색 창(피그마 ⑦-10 · ⑦-10a · ⑦-10c)과 전체 결과 화면(⑦-10d)이 같이 쓴다.
 *
 *   묶음      아이콘      굵은 줄                    아랫줄                          오른쪽
 *   엔티티    섬 색 육각   이름                       웹 · 섬 · 활동도 · 사건 N건      N건
 *   행위자    섬 색 육각   핸들                       웹 · 주 활동 영토 · 사건 N건     N건
 *   사건      시계        [KR · 유통 · 날짜 · 규모]   날짜 · 올라온 곳(행위자 → 영토)  종류 칩
 *   관계      ⇄          출발 → 도착                 종류 · 신뢰도 · N건
 *
 * 설계서 4.2.2 자동완성 표를 따른다. 검색어에 걸린 글자는 굵게 칠한다. 사건 제목에는
 * 이름이 없어 칠할 곳이 아랫줄의 올라온 곳뿐이다.
 *
 * 엔티티 · 행위자 줄 아랫줄 맨 앞에 웹을 적는다 (설계서 4.2.2 「결과에 오픈웹/다크웹
 * 표시」, 5.3 「결과 행에 웹 표시」). 지금 찾는 대상은 다크웹뿐이라 늘 「다크웹」이다.
 * 사건 · 관계 줄에는 안 적는다 — 4.2.2 표가 두 줄에 웹을 두지 않았고, 올라온 영토의
 * 웹을 따라가므로 같은 말을 되풀이하게 된다.
 */

"use client";

import type { ReactNode } from "react";

import { Chip, hexPoints } from "./RelBits";
import { EV_KIND_LABEL, EV_KIND_TONE, dayOf, eventTitle } from "@/lib/events";
import { CONF_LABEL, KIND_NAME } from "@/lib/relations";
import { markAt, type Hit, type Recent, type SearchIndex } from "@/lib/search";
import type { IslandCode, Web } from "@/lib/types";
import { WEB_LABEL, webOfIsland } from "@/lib/web";

/** 줄을 그리는 데 드는 것. 부르는 쪽(`page.tsx`)이 한 번 만들어 넘긴다 */
export type SearchCtx = {
  ix: SearchIndex;
  /** 섬 이름 — 「포럼」 */
  islandName: (id: IslandCode) => string;
  /** 섬 색 토큰 꼬리 — `--t-island-<꼬리>` */
  token: (id: IslandCode) => string;
  /** 기준일 활동도. 그 기준일 지도에 없으면 null */
  activityOf: (id: string) => number | null;
};

/** 검색어에 걸린 글자를 굵게. `at` 을 안 주면 글에서 찾는다 */
export function Marked({ text, needle, at }: { text: string; needle: string; at?: number }) {
  const i = at ?? markAt(text, needle);
  if (i < 0 || !needle) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <span style={{ color: "var(--t-accent)" }}>{text.slice(i, i + needle.length)}</span>
      {text.slice(i + needle.length)}
    </>
  );
}

/** 왼쪽 아이콘 칸 */
export function Tile({ children }: { children: ReactNode }) {
  return (
    <span
      aria-hidden
      className="flex size-[28px] shrink-0 items-center justify-center rounded-[8px] bg-card text-[13px] text-label"
    >
      {children}
    </span>
  );
}

/** 섬 색 육각 아이콘 (⑦-10a 엔티티 줄) */
export function HexIcon({ token }: { token: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14">
      <polygon points={hexPoints(7, 7, 6.5)} fill={`var(--t-island-${token})`} />
    </svg>
  );
}

/** 웹 점 색. 머리띠 웹 전환 탭의 점과 같은 토큰이다 (설계서 6.5 「탭 강조」) */
const WEB_DOT: Record<Web, string> = {
  open: "var(--t-web-open)",
  dark: "var(--t-web-dark)",
};

/** 웹 표시 — 점 하나와 웹 이름. 아랫줄 글 사이에 끼므로 줄 안 요소로 둔다 */
export function WebTag({ web }: { web: Web }) {
  return (
    <>
      <span
        aria-hidden
        className="mr-s1 inline-block size-[6px] rounded-full align-middle"
        style={{ background: WEB_DOT[web] }}
      />
      {WEB_LABEL[web]}
    </>
  );
}

function nameOf(ctx: SearchCtx, id: string): string {
  return ctx.ix.byId.get(id)?.name ?? id;
}

/** 사건이 올라온 곳. 행위자가 올렸으면 「행위자 → 영토」 (4.2.2 사건 줄) */
export function whereText(ctx: SearchCtx, h: Extract<Hit, { kind: "event" }>): string {
  const e = h.ev;
  return e.actorTerritoryId && ctx.ix.byId.has(e.actorTerritoryId)
    ? `${nameOf(ctx, e.actorTerritoryId)} → ${nameOf(ctx, e.territoryId)}`
    : nameOf(ctx, e.territoryId);
}

/** 한 줄에 들어갈 조각. 줄 모양(버튼 · 행)은 부르는 쪽이 정한다 */
export type RowParts = {
  icon: ReactNode;
  title: ReactNode;
  sub: ReactNode;
  side: ReactNode;
};

export function rowParts(ctx: SearchCtx, h: Hit, needle: string): RowParts {
  if (h.kind === "entity" || h.kind === "actor") {
    const e = h.e;
    const title = <Marked text={e.name} needle={needle} at={h.m.at} />;
    const alias = h.m.via ? ` · 별칭 ${h.m.via}` : "";
    const icon = (
      <Tile>
        <HexIcon token={ctx.token(e.islandId)} />
      </Tile>
    );
    const side = (
      <span className="shrink-0 rounded-[6px] border border-edge px-s2 py-[1px] text-[11px] tabular-nums text-label">
        {e.eventCount}건
      </span>
    );
    const web = <WebTag web={webOfIsland(e.islandId)} />;
    if (h.kind === "actor") {
      const main = h.main ? `주 활동 ${nameOf(ctx, h.main)}` : "주 활동 영토 없음";
      return {
        icon,
        title,
        sub: (
          <>
            {web} · {main} · 사건 {e.eventCount}건{alias}
          </>
        ),
        side,
      };
    }
    const a = ctx.activityOf(e.id);
    const act = a === null ? "이 기준일 지도에 없음" : `활동도 ${a}`;
    return {
      icon,
      title,
      sub: (
        <>
          {web} · {ctx.islandName(e.islandId)} · {act} · 사건 {e.eventCount}건{alias}
        </>
      ),
      side,
    };
  }

  if (h.kind === "event") {
    const e = h.ev;
    return {
      icon: <Tile>◷</Tile>,
      title: eventTitle(e),
      sub: (
        <>
          {dayOf(e)} · <Marked text={whereText(ctx, h)} needle={needle} />
        </>
      ),
      side: e.kind ? <Chip tone={EV_KIND_TONE[e.kind]}>{EV_KIND_LABEL[e.kind]}</Chip> : null,
    };
  }

  const r = h.r.rel;
  return {
    icon: <Tile>⇄</Tile>,
    title: (
      <>
        <Marked text={nameOf(ctx, r.from)} needle={needle} /> → <Marked text={nameOf(ctx, r.to)} needle={needle} />
      </>
    ),
    sub: `${KIND_NAME[r.kind]} · ${CONF_LABEL[r.confidence]} · ${h.r.count}건`,
    side: null,
  };
}

/** 고른 결과를 최근 검색 한 줄로 (⑦-10 「Qilin / 랜섬웨어 · 엔티티」) */
export function recentOf(ctx: SearchCtx, h: Hit, at: number): Recent {
  if (h.kind === "entity" || h.kind === "actor") {
    const what = h.kind === "actor" ? "행위자" : "엔티티";
    return { kind: h.kind, id: h.e.id, label: h.e.name, sub: `${ctx.islandName(h.e.islandId)} · ${what}`, at };
  }
  if (h.kind === "event") {
    return { kind: "event", id: h.ev.id, label: eventTitle(h.ev), sub: `사건 · ${dayOf(h.ev)}`, at };
  }
  const r = h.r.rel;
  return {
    kind: "rel",
    id: r.id,
    via: h.via,
    label: `${nameOf(ctx, r.from)} → ${nameOf(ctx, r.to)}`,
    sub: `관계 · ${KIND_NAME[r.kind]}`,
    at,
  };
}

/** 최근 검색 한 줄을 다시 결과로. 그 사이 대상이 없어졌으면 null */
export function hitOfRecent(ix: SearchIndex, r: Recent): Hit | null {
  const m = { rank: 0 as const, at: -1 };
  if (r.kind === "entity" || r.kind === "actor") {
    const e = ix.byId.get(r.id);
    if (!e) return null;
    return r.kind === "actor" ? { kind: "actor", e, m, main: ix.main.get(e.id) ?? null } : { kind: "entity", e, m };
  }
  if (r.kind === "event") {
    const ev = ix.events.find((x) => x.id === r.id);
    return ev ? { kind: "event", ev, rank: 0 } : null;
  }
  const re = ix.rels.find((x) => x.rel.id === r.id);
  return re ? { kind: "rel", r: re, rank: 0, via: r.via ?? re.rel.to } : null;
}

/** 줄의 열쇠. 행위자는 엔티티 묶음에도 같은 영토로 나와 종류를 붙인다 */
export function hitKey(h: Hit): string {
  if (h.kind === "event") return `event:${h.ev.id}`;
  if (h.kind === "rel") return `rel:${h.r.rel.id}`;
  return `${h.kind}:${h.e.id}`;
}
