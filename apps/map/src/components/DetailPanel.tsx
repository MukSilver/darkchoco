/**
 * 오른쪽 상세 패널 — 설계서 4.2.4 · 4.3.1 · 4.3.2. 폭 312, 접힘 48.
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
 */

"use client";

import type { ReactNode } from "react";

import PanelShell from "./PanelShell";
import type { PanelBar, PanelView } from "@/lib/panel";

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
  /** [연결] 탭 본문. 없으면(선택 없음) 탭이 안 눌린다 */
  links: ReactNode | null;
  /** [사건] 탭 본문. 없으면(선택 없음) 탭이 안 눌린다 */
  events: ReactNode | null;
  /** [사건] 탭 배지 — 지금 기간의 건수 (설계서 4.3.2) */
  eventBadge: number | null;
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

      {shown === "links" ? links : shown === "events" ? events : <Overview view={view} />}
    </PanelShell>
  );
}

function Overview({ view }: { view: PanelView }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-s3">
        {view.stats.map((s) => (
          <div key={s.label} className="rounded-[12px] border border-edge bg-card px-s4 py-s4">
            <div className="text-[11px] text-label">{s.label}</div>
            <div className="mt-s1 text-[26px] font-semibold leading-none tabular-nums text-title">
              {s.value}
            </div>
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

      <MonthChart bars={view.months} token={view.barToken} />
    </>
  );
}

/**
 * 「사건 수 · 최근 12개월」 막대. 설계서 4.3.1 · 4.3.2 가 「월별 막대, 실제
 * 건수」라고만 적었다.
 *
 * 마지막 달을 진하게 한다. 피그마에서 오른쪽 끝 막대만 밝다 — 그 달이
 * 지금 보고 있는 기준일이라는 표시다.
 */
function MonthChart({ bars, token }: { bars: PanelBar[]; token: string | null }) {
  const max = Math.max(1, ...bars.map((b) => b.count));
  const color = token ? `var(--t-island-${token})` : "var(--t-accent)";

  return (
    <section className="flex flex-col gap-s3">
      <h3 className="text-[12px] font-semibold text-strong">사건 수 · 최근 12개월</h3>
      <div className="rounded-[12px] border border-edge bg-card px-s4 pb-s3 pt-s4">
        <div className="flex h-[76px] items-end gap-[3px]">
          {bars.map((b, i) => (
            <div
              key={b.label}
              title={`${b.label} · ${b.count}건`}
              className="flex-1 rounded-t-[2px]"
              style={{
                height: `${Math.max(2, (b.count / max) * 100)}%`,
                background: color,
                opacity: i === bars.length - 1 ? 1 : 0.55,
              }}
            />
          ))}
        </div>
        <div className="mt-s2 flex justify-between text-[9px] tabular-nums text-label">
          <span>{bars[0]?.label}</span>
          <span>{bars[bars.length - 1]?.label}</span>
        </div>
      </div>
    </section>
  );
}
