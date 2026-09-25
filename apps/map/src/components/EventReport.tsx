/**
 * 사건 보고서 팝업 — 설계서 4.3.4 (L682-711), 피그마 ⑦-4 하단 · 사건 상세 모달
 * (02 · 07 라이트 블랙), 컴포넌트 시트 Incident Modal · Key Value · Tag · Button.
 *
 *   ‹ 이전 사건                                         닫기 ×
 *   EVENT · 사건 상세 · 더블클릭으로 열림
 *   [KR · 유통 · 2026-05-14 · 255GB]
 *   영토 · 섬 · 게시 시각 (UTC)
 *   [종류] [신뢰도] [위험도] [사건 번호]
 *   ┌ 발생 일시 ─────┬ 엔티티 ───────┐
 *   ├ 게시 위치 ─────┼ 유출 규모 ─────┤
 *   └ 유출 항목 ─────────────────────┘
 *   설명 · 연결된 사건 · 관계 · 출처
 *   마스킹 · 접근 로그 안내      JSON 내보내기   사건 자료 다운로드 (.zip)
 *
 * 무엇을 보일지는 `report.ts` 가 정한다. 여기는 그리기와 누르기만 한다. 「JSON
 * 내보내기」도 같은 모형을 쓴다 — 화면에 없는 칸이 파일에 섞이지 않는다 (L707).
 *
 * 닫기는 닫기 × · 바깥 클릭 · Esc 셋이다 (L684). **Esc 는 부르는 쪽(page.tsx)이 받는다**
 * — 페이지 Esc(선택 해제)보다 먼저 팝업을 닫아야 해서 한 곳에서 가른다.
 * 연결된 사건을 누르면 내용만 바뀌고 뒤 지도는 그대로다. 「‹ 이전 사건」 이 한 칸씩
 * 되돌린다 (L703). 쌓는 것은 부르는 쪽이 한다.
 *
 * 크기는 `--w-modal` 620 × `--h-modal` 803 (tokens.css, 피그마 Final · Layout)이고
 * 창이 작으면 줄인다. 넘치는 본문만 굴린다 — 머리와 바닥 단추는 늘 보인다.
 *
 * 「사건 자료 다운로드 (.zip)」는 구성이 보류라(L706) 단추만 두고 누를 수 없다.
 */

"use client";

import { useEffect, useRef } from "react";

import { Chip } from "./RelBits";
import { CONF_CHIP, CONF_LABEL } from "@/lib/relations";
import { SOURCE_NOTE, reportJson, type EventReportModel, type ReportField } from "@/lib/report";

export type EventReportProps = {
  model: EventReportModel;
  /** 연결된 사건을 타고 들어왔으면 참 — 「‹ 이전 사건」 을 단다 */
  canBack: boolean;
  onBack: () => void;
  onClose: () => void;
  /** 연결된 사건 — 팝업 내용을 그 사건으로 바꾼다 */
  onOpenLinked: (id: string) => void;
  /** 정보 표의 영토 이름 — 팝업을 닫고 지도에서 그 영토를 고른다 (L704) */
  onPickTerritory: (id: string) => void;
  /** 이 사건이 근거인 관계 — 관계 탭 ① 상태로 간다 (4.3.3) */
  onOpenRel: (relId: string) => void;
};

/** 파일 이름에 못 쓰는 글자를 걷는다. 사건 번호는 `LEAK-123` 꼴이라 보통 그대로다 */
function fileName(id: string): string {
  return `${id.replace(/[^\w.-]+/g, "_")}.json`;
}

export default function EventReport({
  model,
  canBack,
  onBack,
  onClose,
  onOpenLinked,
  onPickTerritory,
  onOpenRel,
}: EventReportProps) {
  const dialog = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  // 누르기가 바깥에서 시작했을 때만 닫는다. 본문 글을 끌어 고르다 바깥에서 놓아도 안 닫힌다
  const downOutside = useRef(false);

  // 열리면 팝업에 초점을 옮기고, 닫히면 열기 전 자리로 돌려준다 (키보드로 연 사람)
  useEffect(() => {
    const prev = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog.current?.focus();
    return () => prev?.focus();
  }, []);

  // 연결된 사건으로 바뀌면 본문을 맨 위로 올린다
  useEffect(() => {
    body.current?.scrollTo({ top: 0 });
  }, [model.id]);

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(reportJson(model), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName(model.id);
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  const empty = model.linked.length === 0 && model.relations.length === 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-s5"
      // 뒤 화면을 어둡게 (L684). 모드와 무관하게 검은 막이라 토큰이 없다 — 화이트 판에서도 어두워야 한다
      style={{ background: "rgb(0 0 0 / 0.55)" }}
      onMouseDown={(e) => {
        downOutside.current = e.target === e.currentTarget;
      }}
      onClick={(e) => {
        if (downOutside.current && e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="event-report-title"
        tabIndex={-1}
        className="flex flex-col overflow-hidden rounded-[16px] border border-edge bg-panel shadow-2xl outline-none"
        style={{
          width: "min(var(--w-modal), calc(100vw - 32px))",
          maxHeight: "min(var(--h-modal), calc(100vh - 48px))",
        }}
      >
        <header className="flex shrink-0 flex-col gap-s1 border-b border-divider px-s5 pb-s4 pt-s4">
          <div className="flex items-center gap-s3">
            {canBack && (
              <button
                type="button"
                onClick={onBack}
                className="shrink-0 rounded-[8px] border border-edge px-s2 py-[2px] text-[11px] text-body hover:text-title"
              >
                ‹ 이전 사건
              </button>
            )}
            <span className="min-w-0 flex-1 truncate font-mono text-[11px] tracking-[0.12em] text-label">
              EVENT · 사건 상세 · 더블클릭으로 열림
            </span>
            <button
              type="button"
              onClick={onClose}
              aria-label="사건 상세 닫기"
              className="shrink-0 text-[12px] text-label hover:text-title"
            >
              닫기 ×
            </button>
          </div>
          <h2 id="event-report-title" className="mt-s1 text-[18px] font-semibold leading-snug text-title">
            {model.title}
          </h2>
          <p className="text-[12px] tabular-nums text-label">{model.meta}</p>
        </header>

        <div ref={body} className="flex min-h-0 flex-1 flex-col gap-s5 overflow-y-auto px-s5 py-s4">
          <div className="flex flex-wrap gap-s2">
            {model.chips.map((c) => (
              <Chip key={c.label} tone={c.tone}>
                {c.tag ? <span className="font-mono font-semibold">{c.label}</span> : c.label}
              </Chip>
            ))}
          </div>

          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-[12px] border border-edge bg-divider">
            {model.fields.map((f, i) => (
              <Field
                key={f.label}
                f={f}
                wide={i === model.fields.length - 1 && model.fields.length % 2 === 1}
                onPick={onPickTerritory}
              />
            ))}
          </dl>

          <section className="flex flex-col gap-s2">
            <h3 className="text-[12px] text-label">설명</h3>
            <p className="text-[13px] leading-[1.75] text-body">{model.description}</p>
          </section>

          <section className="flex flex-col gap-s2">
            <h3 className="text-[12px] text-label">연결된 사건 · 관계</h3>
            {empty ? (
              <p className="rounded-[12px] border border-edge px-s4 py-s3 text-[12px] text-label">
                이 사건과 이어진 사건 · 관계가 없습니다.
              </p>
            ) : (
              <ul className="flex flex-col gap-s2">
                {model.linked.map((x) => (
                  <li key={x.id}>
                    <button
                      type="button"
                      onClick={() => onOpenLinked(x.id)}
                      title="이 사건으로 바꿔 보기"
                      className="flex w-full items-center gap-s3 rounded-[12px] border border-edge px-s4 py-s3 text-left hover:border-edge-strong"
                    >
                      <span className="min-w-0 flex-1 truncate text-[13px] text-title">
                        {x.title}
                        <span className="text-label"> · {x.place}</span>
                      </span>
                      <span className="shrink-0 font-mono text-[10px] text-label">{x.id}</span>
                      {x.conf && <Chip tone={CONF_CHIP[x.conf]}>{CONF_LABEL[x.conf]}</Chip>}
                    </button>
                  </li>
                ))}
                {model.relations.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => onOpenRel(r.id)}
                      title="관계 탭에서 이 관계 보기"
                      className="flex w-full items-center gap-s3 rounded-[12px] border border-edge px-s4 py-s3 text-left hover:border-edge-strong"
                    >
                      <span className="min-w-0 flex-1 truncate text-[13px] text-title">
                        {r.route}
                        <span className="text-label"> · {r.kind}</span>
                      </span>
                      <span className="shrink-0 font-mono text-[10px] text-label">{r.id}</span>
                      <Chip tone={CONF_CHIP[r.conf]}>{CONF_LABEL[r.conf]}</Chip>
                      <span aria-hidden className="shrink-0 text-[11px] text-label">
                        관계 탭 ›
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="flex flex-col gap-s2">
            <h3 className="text-[12px] text-label">출처</h3>
            <div className="flex flex-col gap-s1 border-b border-divider pb-s3">
              <span className="text-[13px] font-semibold text-title">{model.source.type}</span>
              <span className="font-mono text-[11px] tabular-nums text-label">{model.source.meta}</span>
            </div>
            <p className="text-[11px] text-label">{SOURCE_NOTE}</p>
          </section>
        </div>

        <footer className="flex shrink-0 items-center gap-s3 border-t border-divider px-s5 py-s4">
          <p className="min-w-0 flex-1 text-[11px] text-label">다운로드 파일 마스킹 처리 · 접근 로그가 기록됩니다</p>
          <button
            type="button"
            onClick={exportJson}
            className="shrink-0 rounded-[10px] border border-edge px-s4 py-s2 text-[12px] text-body hover:border-edge-strong hover:text-title"
          >
            JSON 내보내기
          </button>
          <button
            type="button"
            disabled
            title="보류 — 사건 자료(.zip) 구성을 아직 정하지 않았습니다 (설계서 4.3.4)"
            className="shrink-0 cursor-not-allowed rounded-[10px] bg-accent px-s4 py-s2 text-[12px] font-semibold text-on-accent opacity-50"
          >
            사건 자료 다운로드 (.zip)
          </button>
        </footer>
      </div>
    </div>
  );
}

/** 정보 표 한 칸 (컴포넌트 시트 Key Value). 영토 칸은 누르면 지도로 간다 */
function Field({ f, wide, onPick }: { f: ReportField; wide: boolean; onPick: (id: string) => void }) {
  const territoryId = f.territoryId;
  return (
    <div className={"flex flex-col gap-s1 bg-panel px-s4 py-s3" + (wide ? " col-span-2" : "")}>
      <dt className="text-[11px] text-label">{f.label}</dt>
      <dd className="min-w-0 text-[14px] text-title">
        {territoryId ? (
          <button
            type="button"
            onClick={() => onPick(territoryId)}
            title="팝업을 닫고 지도에서 이 영토 고르기"
            className="text-left hover:underline"
          >
            {f.value}
            <span aria-hidden className="ml-s1 text-label">
              ›
            </span>
          </button>
        ) : f.items ? (
          <span className="flex flex-wrap gap-s1">
            {f.items.map((x) => (
              <Chip key={x} tone="neutral">
                {x}
              </Chip>
            ))}
          </span>
        ) : (
          <span className="break-words tabular-nums">{f.value}</span>
        )}
      </dd>
    </div>
  );
}
