/**
 * 오른쪽 상세 패널 — 설계서 4.2.4 · 4.3.1 · 4.3.2 · 4.3.8. 폭 312, 접힘 48.
 *
 * **첫 진입을 펼침으로 뒀다. 설계서 본문과 다르다.** 본문 표는 「첫 진입
 * (선택 없음) → 접힘」인데, 피그마 `⑦-1 섬 지도 (기본)` 은 패널이 펼쳐진 채
 * 생태계 전체 정보를 보여 준다. **어긋나면 피그마를 따르기로 했다**
 * (2026-09-22, 최현서).
 *
 * 무엇을 보여 줄지는 `panel.ts` 가 정한다. 여기는 그리기만 한다.
 *
 * 탭은 개요 / 사건 / 연결 셋이다. 사건 탭은 `EventsTab`, 연결 탭은 `LinksTab` 이
 * 그린다. 사건 제목은 분류 칸으로 새로 지은 것이다 (2026-09-25, `events.ts`).
 * 다른 영토를 눌러도 열려 있던 탭을 그대로 둔다 (설계서 4.2.3).
 *
 * 선택이 없어도 [사건] · [연결] 이 눌린다 — 피그마 ⑦-1 이 「사건 5 · 연결 18」 로
 * 탭을 살려 두었다. 설계서는 섬 · 영토 탭만 적어 두어 피그마를 따랐다.
 */

"use client";

import type { ReactNode } from "react";

import PanelShell from "./PanelShell";
import { monthTicks, type PanelActivity, type PanelBar, type PanelView } from "@/lib/panel";

export type PanelTabKey = "overview" | "events" | "links";

const TABS = [
  { key: "overview", name: "개요" },
  { key: "events", name: "사건" },
  { key: "links", name: "연결" },
] as const;

export type DetailPanelProps = {
  view: PanelView;
  open: boolean;
  onToggle: (open: boolean) => void;
  tab: PanelTabKey;
  onTab: (k: PanelTabKey) => void;
  /** [연결] 탭 본문. 없으면 탭이 안 눌린다 */
  links: ReactNode | null;
  /** [사건] 탭 본문. 없으면 탭이 안 눌린다 */
  events: ReactNode | null;
  /** [사건] 탭 배지 — 지금 기간의 건수 (설계서 4.3.2) */
  eventBadge: number | null;
  /**
   * 사건 보고서 팝업 열기 (설계서 4.3.4). [개요] 「공식 발표 사고」 최근 1건이 부른다.
   * 넘기지 않으면 그 줄은 눌리지 않는 글이다
   */
  onOpenEvent?: (id: string) => void;
  /** 행위자 [개요]의 활동 영토를 눌렀을 때 — 그 영토를 고른다 (설계서 4.3.8) */
  onPickTerritory?: (id: string) => void;
};

export default function DetailPanel({
  view,
  open,
  onToggle,
  tab,
  onTab,
  links,
  events,
  eventBadge,
  onOpenEvent,
  onPickTerritory,
}: DetailPanelProps) {
  // 보일 것이 없는 탭이 열려 있으면 개요로 보인다. 탭 상태는 그대로 둔다 —
  // 다시 영토를 고르면 그 탭으로 돌아온다
  const body = { overview: true, events: events !== null, links: links !== null };
  const shown: PanelTabKey = body[tab] ? tab : "overview";

  return (
    <PanelShell
      open={open}
      onToggle={onToggle}
      header={{
        kindLabel: view.kindLabel,
        kindToken: view.kindToken,
        stateLabel: view.stateLabel,
        title: view.title,
        subtitle: view.subtitle,
      }}
    >
      <nav aria-label="패널 탭" className="flex gap-s5 border-b border-divider">
        {TABS.map((t) => {
          const on = t.key === shown;
          const enabled = body[t.key];
          const badge =
            t.key === "events"
              ? (eventBadge ?? view.eventCount)
              : t.key === "links"
                ? view.linkCount
                : null;
          return (
            <button
              key={t.key}
              type="button"
              disabled={!enabled}
              aria-current={on ? "page" : undefined}
              onClick={() => {
                if (enabled) onTab(t.key);
              }}
              title={enabled ? undefined : "섬이나 영토를 고르면 보입니다"}
              className={[
                "-mb-px border-b-2 pb-s3 text-[13px]",
                on
                  ? "border-[var(--t-accent)] font-semibold text-strong"
                  : "border-transparent text-label disabled:cursor-not-allowed",
                !on && enabled ? "hover:text-body" : "",
              ].join(" ")}
            >
              {t.name}
              {badge !== null && <span className="ml-s2 text-[11px] tabular-nums">{badge}</span>}
            </button>
          );
        })}
      </nav>

      {shown === "links" ? (
        links
      ) : shown === "events" ? (
        events
      ) : (
        <Overview view={view} onOpenEvent={onOpenEvent} onPickTerritory={onPickTerritory} />
      )}
    </PanelShell>
  );
}

function Overview({
  view,
  onOpenEvent,
  onPickTerritory,
}: {
  view: PanelView;
  onOpenEvent?: (id: string) => void;
  onPickTerritory?: (id: string) => void;
}) {
  return (
    <>
      <div className="grid grid-cols-2 gap-s3">
        {view.stats.map((s) => (
          <div key={s.label} className="rounded-[12px] border border-edge bg-card px-s4 py-s4">
            <div className="text-[11px] text-label">{s.label}</div>
            <div className="mt-s1 text-[26px] font-semibold leading-none tabular-nums text-title">
              {s.value}
            </div>
            {s.raw && <div className="mt-s2 truncate text-[11px] tabular-nums text-body">{s.raw}</div>}
            {s.note && (
              <div className="mt-s2 flex items-baseline gap-s1 text-[11px] tabular-nums">
                {s.trend !== undefined && s.trend !== 0 && (
                  <span
                    style={{
                      color: s.trend > 0 ? "var(--t-trend-up)" : "var(--t-trend-down)",
                    }}
                  >
                    {s.trend > 0 ? "▲" : "▼"}
                    {s.trendText ?? Math.abs(Math.round(s.trend))}
                  </span>
                )}
                <span className="text-label">{s.note}</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {view.actor && view.actor.info.length > 0 && (
        <section className="flex flex-col gap-s3">
          <h3 className="text-[12px] font-semibold text-strong">행위자 정보</h3>
          <dl className="flex flex-col divide-y divide-divider rounded-[12px] border border-edge bg-card px-s4">
            {view.actor.info.map((r) => (
              <div key={r.label} className="flex gap-s3 py-s3 text-[12px]">
                <dt className="w-[72px] shrink-0 text-label">{r.label}</dt>
                <dd className="min-w-0 flex-1 break-words text-body">{r.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {view.actor && (
        <section className="flex flex-col gap-s3">
          <div className="flex items-baseline justify-between">
            <h3 className="text-[12px] font-semibold text-strong">주 활동 영토</h3>
            <span className="text-[10px] text-label">사건 수</span>
          </div>
          {view.actor.main ? (
            <ul className="flex flex-col gap-s2">
              <ActivityRow row={view.actor.main} main onPick={onPickTerritory} />
              {view.actor.others.map((r) => (
                <ActivityRow key={r.territoryId} row={r} onPick={onPickTerritory} />
              ))}
            </ul>
          ) : (
            <p className="rounded-[12px] border border-edge bg-card px-s4 py-s4 text-[12px] text-label">
              이 기준일까지 활동한 영토가 없습니다.
            </p>
          )}
        </section>
      )}

      {view.description && (
        <section className="flex flex-col gap-s3">
          <h3 className="text-[12px] font-semibold text-strong">{view.descTitle}</h3>
          <p className="text-[12px] leading-[1.75] text-body">{view.description}</p>
        </section>
      )}

      {view.shares && view.shares.length > 0 && (
        <section className="flex flex-col gap-s3">
          <div className="flex items-baseline justify-between">
            <h3 className="text-[12px] font-semibold text-strong">{view.sharesTitle}</h3>
            <span className="text-[10px] text-label">전체 대비</span>
          </div>
          <ul className="flex flex-col gap-s4">
            {view.shares.map((s) => (
              <li key={s.name} className="flex flex-col gap-s2">
                <div className="flex items-center gap-s2">
                  {!view.barToken && (
                    <span
                      aria-hidden
                      className="size-[8px] shrink-0 rounded-full"
                      style={{
                        background: `var(--t-island-${s.token}-legend, var(--t-island-${s.token}))`,
                      }}
                    />
                  )}
                  <span className="flex-1 text-[12px] text-body">{s.name}</span>
                  <span className="text-[12px] font-semibold tabular-nums text-strong">
                    {s.percent}%
                  </span>
                </div>
                <div className="h-[4px] overflow-hidden rounded-full bg-bar-track">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${s.percent}%`,
                      background: `var(--t-island-${s.token})`,
                    }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {view.official && <OfficialBlock o={view.official} onOpen={onOpenEvent} />}

      <MonthChart bars={view.months} token={view.barToken} />
    </>
  );
}

/**
 * 활동 영토 한 줄 — 섬 색 점, 이름, 건수. 주 활동 영토는 「주」 표시를 단다.
 * 누르면 그 영토를 고른다 (설계서 4.3.8 「주 활동 영토, 나머지 활동 영토」)
 */
function ActivityRow({
  row,
  main = false,
  onPick,
}: {
  row: PanelActivity;
  main?: boolean;
  onPick?: (id: string) => void;
}) {
  const inner = (
    <>
      <span
        aria-hidden
        className="size-[8px] shrink-0 rounded-full"
        style={{ background: `var(--t-island-${row.token}-legend, var(--t-island-${row.token}))` }}
      />
      <span className="min-w-0 flex-1 truncate text-left text-[12px] text-body">{row.name}</span>
      {main && (
        <span className="shrink-0 rounded-[6px] border border-accent-edge bg-accent-subtle px-s2 py-[1px] text-[10px] text-title">
          주
        </span>
      )}
      <span className="shrink-0 text-[12px] font-semibold tabular-nums text-strong">{row.count}건</span>
    </>
  );
  return (
    <li>
      {onPick ? (
        <button
          type="button"
          onClick={() => onPick(row.territoryId)}
          title={`${row.name} 고르기`}
          className="flex w-full items-center gap-s2 rounded-[10px] border border-edge bg-card px-s3 py-s2 hover:border-edge-strong"
        >
          {inner}
        </button>
      ) : (
        <div className="flex items-center gap-s2 rounded-[10px] border border-edge bg-card px-s3 py-s2">{inner}</div>
      )}
    </li>
  );
}

/**
 * 「공식 발표 사고」 절 (설계서 4.3.2 — 유출 사고 DB 건수와 최근 1건). 최근 1건은
 * 공표일 · 규모 · 분류 칸으로 지은 제목이다. 조직명은 안 싣는다 (2026-09-26).
 *
 * 최근 1건을 누르면 보고서 팝업(4.3.4)이 열린다. `onOpen` 이 없으면 눌리지 않는
 * 글로 둔다.
 */
function OfficialBlock({
  o,
  onOpen,
}: {
  o: NonNullable<PanelView["official"]>;
  onOpen?: (id: string) => void;
}) {
  const latest = o.latest;
  // 게시에 붙은 사고(G-9)는 공표일이 빌 수 있고 규모를 안 적는다 (`officialOf`)
  const meta = latest
    ? [latest.day ? `공표 ${latest.day}` : "공표 기록 없음", latest.size ? `규모 ${latest.size}` : null]
        .filter(Boolean)
        .join(" · ")
    : "";
  const card = latest && (
    <>
      <span className="text-[10px] text-label">최근 1건</span>
      <span className="truncate text-[13px] font-semibold text-title">{latest.title}</span>
      <span className="font-mono text-[11px] tabular-nums text-label">{meta}</span>
    </>
  );
  return (
    <section className="flex flex-col gap-s3">
      <div className="flex items-baseline justify-between">
        <h3 className="text-[12px] font-semibold text-strong">공식 발표 사고</h3>
        <span className="text-[11px] tabular-nums text-label">{o.count}건</span>
      </div>
      {!latest ? (
        <p className="rounded-[12px] border border-edge bg-card px-s4 py-s3 text-[12px] text-label">
          이 기준일까지 기록된 공식 발표 사고가 없습니다.
        </p>
      ) : onOpen ? (
        <button
          type="button"
          onClick={() => onOpen(latest.id)}
          className="flex flex-col gap-s1 rounded-[12px] border border-edge bg-card px-s4 py-s3 text-left hover:border-edge-strong"
        >
          {card}
        </button>
      ) : (
        <div className="flex flex-col gap-s1 rounded-[12px] border border-edge bg-card px-s4 py-s3">{card}</div>
      )}
    </section>
  );
}

/**
 * 「사건 수 · 최근 12개월」 막대. 설계서 4.3.1 · 4.3.2 가 「월별 막대, 실제
 * 건수」라고만 적었다. 모양은 피그마 컴포넌트 `Bar Chart · 월별 막대` 를 따른다 —
 * 「마지막 달만 진하게(나머지 34%)」, 막대 사이 4, 축 이름표 넷.
 *
 * 마지막 달이 지금 보고 있는 기준일이라 그 막대만 밝다. 섬 · 영토를 고르면 섬 색,
 * 선택이 없으면 강조색이다 (⑦-1 · ⑦-2 · ⑦-11b).
 *
 * 축 이름표는 이름 붙인 달의 막대 밑에 둔다(`monthTicks`). 피그마는 넷을 폭에 고르게
 * 벌렸는데, 막대가 폭을 다 채우면 이름표가 제 달과 어긋나 보여서다.
 */
function MonthChart({ bars, token }: { bars: PanelBar[]; token: string | null }) {
  const max = Math.max(1, ...bars.map((b) => b.count));
  const color = token ? `var(--t-island-${token})` : "var(--t-accent)";
  const ticks = new Set(monthTicks(bars.length));

  return (
    <section className="flex flex-col gap-s3">
      <h3 className="text-[12px] font-semibold text-strong">사건 수 · 최근 12개월</h3>
      <div className="rounded-[12px] border border-edge bg-card px-s4 pb-s3 pt-s4">
        <div className="flex h-[76px] items-end gap-[4px]">
          {bars.map((b, i) => (
            <div
              key={b.label}
              title={`${b.label} · ${b.count}건`}
              className="flex-1 rounded-t-[3px]"
              style={{
                height: `${Math.max(2, (b.count / max) * 100)}%`,
                background: color,
                opacity: i === bars.length - 1 ? 1 : 0.34,
              }}
            />
          ))}
        </div>
        <div aria-hidden className="mt-s2 flex h-[12px] gap-[4px] font-mono text-[9px] tabular-nums text-label">
          {bars.map((b, i) => (
            <div key={b.label} className="relative flex-1">
              {ticks.has(i) &&
                (i === 0 ? (
                  <span className="absolute left-0 top-0 whitespace-nowrap">{b.label}</span>
                ) : i === bars.length - 1 ? (
                  <span className="absolute right-0 top-0 whitespace-nowrap">{b.label}</span>
                ) : (
                  <span className="absolute left-1/2 top-0 -translate-x-1/2 whitespace-nowrap">{b.label}</span>
                ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
