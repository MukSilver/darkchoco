// 지난 질문 패널 (피그마 B안 「지난 질문 패널」). 이 탭에서 받은 답을 다시 본다. 눌러도 질의 서버를 부르지 않는다.
// 넓은 화면: 왼쪽 칸. 테두리에 걸친 둥근 단추로 접고 편다 (생태계 지도의 옆 패널과 같은 방식). 접으면 좁은 띠만 남는다.
// 좁은 화면: 헤더의 단추로 여는 왼쪽 서랍.
import { useEffect } from 'react'
import type { Past } from '../history'
import type { DoneKind } from '../types'

const KIND: Record<DoneKind, string> = { prepared: '예시', reused: '앞서 만든 답', new: '새 답', no_evidence: '근거 없음' }

const hhmm = (at: number) => new Date(at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })

export function HistoryIcon() {
  return (
    <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2.2 8a5.8 5.8 0 1 0 1.7-4.1" />
      <path d="M2 2.6v2.6h2.6" />
      <path d="M8 5.2V8l1.9 1.3" />
    </svg>
  )
}

function Chevron({ left }: { left: boolean }) {
  return (
    <svg viewBox="0 0 12 12" className="size-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={left ? 'M7.5 2.5 4 6l3.5 3.5' : 'M4.5 2.5 8 6l-3.5 3.5'} />
    </svg>
  )
}

function Body({ list, activeId, onPick, onClear }: {
  list: Past[]; activeId: string | null; onPick: (p: Past) => void; onClear: () => void
}) {
  return (
    <>
      <div className="flex shrink-0 items-center gap-2 px-4 pt-[18px] pb-3">
        <span className="text-[12px] leading-none font-medium tracking-[1.2px] text-muted">지난 질문</span>
        {list.length > 0 && <span className="font-mono text-[11.5px] leading-none text-faint">{list.length}</span>}
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-2 pb-2">
        {list.length === 0 && (
          <p className="px-2 pt-1 text-[13px] leading-[1.6] text-faint">아직 물어본 것이 없어요. 답을 받으면 여기에 쌓여요.</p>
        )}
        {list.map((p) => {
          const on = p.turn.id === activeId
          return (
            <button
              key={p.turn.id}
              type="button"
              onClick={() => onPick(p)}
              aria-current={on ? 'true' : undefined}
              className={`flex w-full shrink-0 cursor-pointer flex-col gap-[6px] rounded-[10px] border px-3 py-[10px] text-left transition-colors ${
                on ? 'border-accent/45 bg-accent/[0.12]' : 'border-transparent hover:bg-card'
              }`}
            >
              <span className={`line-clamp-2 text-[13.5px] leading-[1.45] ${on ? 'text-highlight-text' : 'text-title'}`}>{p.turn.question}</span>
              <span className="flex items-center gap-[6px] text-[11.5px] leading-none text-faint">
                {p.turn.kind && <span>{KIND[p.turn.kind]}</span>}
                {p.turn.kind && <span>·</span>}
                <span className="font-mono">{hhmm(p.at)}</span>
              </span>
            </button>
          )
        })}
      </div>
      <div className="flex shrink-0 items-center justify-between gap-2 border-t border-divider px-4 py-3">
        <p className="text-[11.5px] leading-[1.5] text-faint">이 탭에만 남아요. 탭을 닫으면 사라져요.</p>
        {list.length > 0 && (
          <button type="button" onClick={onClear} className="shrink-0 cursor-pointer text-[12px] leading-none whitespace-nowrap text-muted hover:text-title">모두 지우기</button>
        )}
      </div>
    </>
  )
}

export function HistoryPanel({ list, activeId, open, onToggle, drawer, onDrawer, onPick, onClear }: {
  list: Past[]
  activeId: string | null
  open: boolean                       // 넓은 화면에서 펴져 있는가
  onToggle: () => void
  drawer: boolean                     // 좁은 화면에서 서랍이 열려 있는가
  onDrawer: (v: boolean) => void
  onPick: (p: Past) => void
  onClear: () => void
}) {
  useEffect(() => {
    if (!drawer) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onDrawer(false) }
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [drawer, onDrawer])

  return (
    <>
      {/* 넓은 화면 */}
      <aside
        aria-label="지난 질문"
        className={`relative z-[5] hidden shrink-0 flex-col border-r border-divider bg-panel transition-[width] duration-150 lg:flex ${open ? 'w-[264px]' : 'w-[52px]'}`}
      >
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-label={open ? '지난 질문 접기' : '지난 질문 펴기'}
          className="absolute top-[14px] -right-[13px] flex size-[26px] cursor-pointer items-center justify-center rounded-full border border-line bg-panel text-muted hover:text-title"
        >
          <Chevron left={open} />
        </button>
        {open ? (
          <Body list={list} activeId={activeId} onPick={onPick} onClear={onClear} />
        ) : (
          <button
            type="button"
            onClick={onToggle}
            aria-label={`지난 질문 ${list.length}개 펴기`}
            className="flex flex-1 cursor-pointer flex-col items-center gap-2 pt-[52px] text-muted hover:text-title"
          >
            <HistoryIcon />
            {list.length > 0 && <span className="font-mono text-[11.5px] leading-none">{list.length}</span>}
          </button>
        )}
      </aside>

      {/* 좁은 화면: 서랍. 뒤를 누르면 닫힌다 */}
      {drawer && (
        <>
          <div className="fixed inset-0 z-20 bg-black/50 lg:hidden" onClick={() => onDrawer(false)} aria-hidden="true" />
          <aside aria-label="지난 질문" className="fixed inset-y-0 left-0 z-30 flex w-[min(300px,86vw)] flex-col border-r border-divider bg-panel lg:hidden">
            <button
              type="button"
              onClick={() => onDrawer(false)}
              aria-label="닫기"
              className="absolute top-3 right-3 flex size-[30px] cursor-pointer items-center justify-center rounded-[8px] border border-line text-[16px] leading-none text-muted hover:text-title"
            >
              ×
            </button>
            <Body list={list} activeId={activeId} onPick={(p) => { onDrawer(false); onPick(p) }} onClear={onClear} />
          </aside>
        </>
      )}
    </>
  )
}
