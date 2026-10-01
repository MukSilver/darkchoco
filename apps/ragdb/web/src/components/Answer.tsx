// 답 화면의 가운데 (피그마 「답 · 끝」 30:467, 「출처 원문 열림」 12:296).
// 진행 단계 → 답 글과 출처 번호 → 정보줄 → 출처 카드. 근거 없음과 오류는 카드로 따로 보인다.
import { useState } from 'react'
import { KIND_LABEL, TONE_TEXT, errorMessage, shortDate, statusTone } from '../lib/labels'
import type { Tone } from '../lib/labels'
import { masked } from '../lib/mask'
import type { Source } from '../types'
import type { Phase, Turn } from '../useAsk'

/* ── 진행 단계 (5:47). 지금 단계는 파랑이고 점이 1초 주기로 깜빡임 ── */
const STEPS = ['받음', '찾는 중', '답 쓰는 중', '끝']
const AT: Record<Phase, number> = { received: 0, searching: 1, writing: 2, done: 3, error: -1 }

export function Progress({ turn }: { turn: Turn }) {
  const at = turn.phase === 'error' ? -1 : AT[turn.phase]
  return (
    <ol className="flex flex-wrap items-center gap-3" aria-label="진행 단계">
      {STEPS.map((name, i) => {
        const state = turn.phase === 'error' ? 'idle' : i < at ? 'past' : i === at ? 'now' : 'idle'
        const dot = state === 'past' ? 'bg-body' : state === 'now' ? 'bg-accent' : 'bg-step-idle'
        const color = state === 'past' ? 'text-body' : state === 'now' ? 'text-accent' : 'text-step-idle'
        return (
          <li key={name} className="flex items-center gap-3" aria-current={state === 'now' ? 'step' : undefined}>
            {i > 0 && <span className="h-px w-7 bg-line" />}
            <span className="flex items-center gap-[7px]">
              <span className={`size-[6px] shrink-0 rounded-full ${dot} ${state === 'now' && turn.phase !== 'done' ? 'animate-pulse-dot' : ''}`} />
              <span className={`text-[12.5px] leading-none whitespace-nowrap ${color}`}>{name}</span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}

/* ── 출처 번호 (4:6). 누르면 출처 원문 패널이 열리고 열린 번호는 선택 상태 ── */
function Cite({ n, selected, onClick }: { n: number; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`출처 ${n} 열기`}
      aria-pressed={selected}
      className={`mx-[2px] inline-flex size-[18px] cursor-pointer items-center justify-center rounded-[5px] border align-[0.1em] font-mono text-[11px] leading-none ${
        selected ? 'border-accent font-semibold text-accent-text' : 'border-mask-line text-muted hover:border-accent hover:text-accent-text'
      }`}
    >
      {n}
    </button>
  )
}

/* ── 상태 표시 (4:18) ── */
const DOT: Record<Exclude<Tone, 'plain'>, string> = { online: 'bg-online', offline: 'bg-offline', unknown: 'bg-unknown' }

export function Status({ status }: { status: string | null }) {
  if (!status) return null
  const tone = statusTone(status)
  return (
    <span className="flex items-center gap-[6px]">
      {tone !== 'plain' && (
        <span className={`size-[6px] shrink-0 rounded-full ${DOT[tone]}`} />
      )}
      <span className={`text-[12.5px] leading-none whitespace-nowrap ${TONE_TEXT[tone]}`}>{status}</span>
    </span>
  )
}

/* ── 출처 카드 (5:30) ── */
function SourceCard({ s, selected, onClick }: { s: Source; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`flex w-full cursor-pointer items-center gap-[14px] rounded-[12px] border bg-card px-[14px] py-3 text-left transition-colors ${
        selected ? 'border-accent' : 'border-line-card hover:border-line'
      }`}
    >
      <span className={`w-[22px] shrink-0 text-center font-mono text-[12px] leading-none ${selected ? 'text-accent-text' : 'text-muted'}`}>{s.n}</span>
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className="flex min-w-0 items-center gap-1 text-[14.5px] leading-normal">
          <span className="shrink-0 text-muted">{KIND_LABEL[s.kind] ?? s.kind} ·</span>
          <span className="truncate font-medium text-title">{masked(s.title)}</span>
        </span>
        <span className="truncate text-[12.5px] leading-normal text-faint">{masked(s.section)}</span>
      </span>
      <span className="flex shrink-0 flex-col items-end gap-[5px]">
        <Status status={s.status} />
        <span className="font-mono text-[11px] leading-none text-faint">{shortDate(s.observed_at)}</span>
      </span>
    </button>
  )
}

/* ── 답 ── */
export function Answer({ turn, selected, onCite }: { turn: Turn; selected: number | null; onCite: (n: number) => void }) {
  const [copied, setCopied] = useState(false)
  const done = turn.phase === 'done'

  if (turn.phase === 'error' && turn.error) {
    const m = errorMessage(turn.error.code)
    return (
      <div role="alert" className="flex animate-rise flex-col gap-2 rounded-[16px] border border-danger/30 bg-danger/[0.08] px-6 py-[22px]">
        <p className="text-[16px] leading-normal font-semibold text-title">{m.title}</p>
        <p className="text-[14px] leading-[1.6] text-body">{m.body}</p>
      </div>
    )
  }

  if (done && turn.kind === 'no_evidence') {
    return (
      <div className="flex animate-rise flex-col gap-2 rounded-[16px] border border-line-card bg-card/60 px-6 py-[22px]">
        <p className="text-[16px] leading-normal font-semibold text-title">확인 가능한 근거를 찾지 못했습니다</p>
        <p className="text-[14px] leading-[1.6] text-body">분야, 시기, 장소, 행위자로 바꿔 물어 보세요. 피해 조직의 이름으로는 찾을 수 없어요.</p>
      </div>
    )
  }

  const copy = async () => {
    const lines = turn.sentences.map((s) => s.text + (s.sources.length ? ` [${s.sources.join(', ')}]` : ''))
    const src = turn.sources.map((s) => `[${s.n}] ${KIND_LABEL[s.kind] ?? s.kind} · ${s.title} · ${s.section} (${s.date_label} ${s.observed_at ?? '없음'})`)
    try {
      await navigator.clipboard.writeText([...lines, '', ...src].join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* 복사 권한 없음 */ }
  }

  const badge = turn.kind === 'prepared' ? '미리 검토한 답' : turn.kind === 'reused' ? '같은 질문에 앞서 만든 답' : null

  return (
    <div className="flex w-full flex-col gap-[14px]">
      {badge && (
        <span className="flex items-center gap-2 self-start rounded-full border border-accent/25 bg-accent/[0.12] px-3 py-[5px]">
          <span className="size-[6px] shrink-0 rounded-full bg-accent" />
          <span className="text-[12.5px] leading-none whitespace-nowrap text-accent-text">{badge}</span>
        </span>
      )}

      <div className="text-[16px] leading-[1.7] whitespace-pre-line text-answer" aria-live="polite">
        {done
          ? turn.sentences.map((s, i) => (
              <span key={i}>
                {masked(s.text)}
                {s.sources.map((n) => <Cite key={n} n={n} selected={selected === n} onClick={() => onCite(n)} />)}{' '}
              </span>
            ))
          : turn.text
            ? masked(turn.text)
            : <span className="text-muted">{turn.phase === 'searching' ? '조사 기록에서 찾고 있어요…' : '질문을 받았어요…'}</span>}
      </div>

      {done && turn.piiMasked && (
        <p className="text-[12.5px] leading-normal text-faint">질문에 든 개인정보는 가린 뒤에 찾았어요. 이 답은 다시 쓰이지 않아요.</p>
      )}
      {done && turn.truncated && <p className="text-[12.5px] leading-normal text-faint">답이 길어 중간에서 끊겼어요.</p>}

      {done && (
        <div className="flex items-center gap-[14px] text-[12.5px] leading-normal text-faint">
          <span>출처 {turn.sources.length}개</span>
          {turn.seconds !== null && <span>{turn.seconds}초</span>}
          <span className="flex-1" />
          <button type="button" onClick={copy} className="cursor-pointer rounded-[8px] px-[9px] py-1 text-muted hover:bg-card hover:text-title">
            {copied ? '복사했어요' : '복사'}
          </button>
        </div>
      )}

      {done && turn.sources.length > 0 && (
        <section className="flex w-full flex-col gap-2" aria-label="출처">
          <h2 className="border-t border-divider pt-[14px] text-[12px] leading-none font-medium tracking-[1.2px] text-muted">출처 {turn.sources.length}</h2>
          {turn.sources.map((s) => <SourceCard key={s.n} s={s} selected={selected === s.n} onClick={() => onCite(s.n)} />)}
          <p className="pt-1 pl-[2px] text-[12.5px] leading-[1.6] text-faint">조직 이름과 주소는 가려져 있어요. 질문과 가까운 자료 다섯 개로 답해요. 전부가 아닐 수 있어요.</p>
        </section>
      )}
    </div>
  )
}
