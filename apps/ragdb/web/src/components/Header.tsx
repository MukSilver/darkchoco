// 앱 헤더와 그 아래 안내 띠 (피그마 「앱 헤더」 6:35, 「하루 차단기 안내」 6:36, 「서버 꺼짐 안내」 47:366).
// 로고를 누르면 첫 화면. 판은 지금 쓰는 판. 오른쪽은 /api/status 결과: 정상, 하루 차단기, 서버 꺼짐.
import dotOk from '../assets/dots/header-ok.svg'
import dotBudget from '../assets/dots/header-budget.svg'
import dotOff from '../assets/dots/header-off.svg'

export type ServerState = 'ok' | 'budget' | 'off' | 'loading'

const STATE: Record<Exclude<ServerState, 'loading'>, { dot: string; text: string }> = {
  ok: { dot: dotOk, text: '새 질문 받는 중' },
  budget: { dot: dotBudget, text: '오늘 새 답변은 쉬어요' },
  off: { dot: dotOff, text: '지금은 새 질문을 받지 않아요' },
}

export function Header({ version, server, onHome }: { version: string | null; server: ServerState; onHome: () => void }) {
  const s = server === 'loading' ? null : STATE[server]
  return (
    <header className="sticky top-0 z-10 flex shrink-0 items-center justify-between border-b border-white/[0.06] bg-page/70 px-6 py-[14px] backdrop-blur-[6px]">
      <div className="flex items-center gap-3">
        <button type="button" onClick={onHome} className="flex cursor-pointer items-center gap-3" aria-label="첫 화면으로">
          <span className="size-[10px] rounded-[2px] bg-accent" />
          <span className="text-[15px] leading-none font-bold tracking-[-0.15px] whitespace-nowrap text-title">다크웹 RAG DB</span>
        </button>
        {version && (
          <span className="rounded-full border border-line px-[9px] py-[3px] font-mono text-[11.5px] leading-none whitespace-nowrap text-muted">
            판 {version.slice(0, 8)}
          </span>
        )}
      </div>
      {s && (
        <div className="flex items-center gap-2" role="status">
          <span className="relative size-[7px] shrink-0"><img alt="" src={s.dot} className="absolute inset-0 block size-full max-w-none" /></span>
          <span className="text-[13px] leading-none whitespace-nowrap text-muted">{s.text}</span>
        </div>
      )}
    </header>
  )
}

/** 헤더 아래 띠. 하루 차단기는 노랑, 서버 꺼짐은 빨강. */
export function Banner({ server }: { server: ServerState }) {
  if (server === 'budget') {
    return (
      <div className="shrink-0 border-b border-unknown bg-unknown px-6 py-[10px]">
        <p className="text-[13px] leading-normal font-bold text-[#422c02]">오늘은 새 답변이 쉬어요. 예시 질문과 출처 원문은 그대로 볼 수 있어요.</p>
      </div>
    )
  }
  if (server === 'off') {
    return (
      <div className="shrink-0 border-b border-danger bg-danger px-6 py-[10px]">
        <p className="text-[13px] leading-normal font-bold text-[#4a0b0b]">지금은 새 질문을 받지 않아요. 예시 질문과 출처 원문은 그대로 볼 수 있어요.</p>
      </div>
    )
  }
  return null
}
