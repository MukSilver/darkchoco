// 앱 헤더와 그 아래 안내 띠 (피그마 「앱 헤더」 6:35, 「하루 차단기 안내」 6:36, 「서버 꺼짐 안내」 47:366).
// 점은 색 값(토큰)으로 그린다. 색 안(A안, B안)이 바뀌어도 따라가게 그림 파일을 쓰지 않는다.
// 로고를 누르면 첫 화면. 판은 지금 쓰는 판. 오른쪽은 /api/status 결과: 정상, 하루 차단기, 서버 꺼짐.

import { HistoryIcon } from './HistoryPanel'

export type ServerState = 'ok' | 'budget' | 'off' | 'loading'

const STATE: Record<Exclude<ServerState, 'loading'>, { dot: string; text: string }> = {
  ok: { dot: 'bg-online', text: '새 질문 받는 중' },
  budget: { dot: 'bg-unknown', text: '오늘 새 답변은 쉬어요' },
  off: { dot: 'bg-danger', text: '지금은 새 질문을 받지 않아요' },
}

export function Header({ version, server, onHome, history, onHistory }: {
  version: string | null; server: ServerState; onHome: () => void; history: number; onHistory: () => void
}) {
  const s = server === 'loading' ? null : STATE[server]
  return (
    <header className="sticky top-0 z-10 flex shrink-0 items-center justify-between border-b border-white/[0.06] bg-page/70 px-6 py-[14px] backdrop-blur-[6px]">
      <div className="flex items-center gap-3">
        {/* 좁은 화면에서 지난 질문 서랍을 여는 단추. 넓은 화면은 왼쪽 칸이 늘 있다 */}
        <button
          type="button"
          onClick={onHistory}
          aria-label={`지난 질문 ${history}개`}
          className="flex h-[30px] cursor-pointer items-center gap-[6px] rounded-[8px] border border-line px-2 text-muted hover:text-title lg:hidden"
        >
          <HistoryIcon />
          {history > 0 && <span className="font-mono text-[11.5px] leading-none">{history}</span>}
        </button>
        <button type="button" onClick={onHome} className="flex cursor-pointer items-center gap-3" aria-label="첫 화면으로">
          <span className="size-[10px] rounded-[2px] bg-accent" />
          <span className="text-[15px] leading-none font-semibold tracking-[-0.15px] whitespace-nowrap text-title">다크웹 RAG DB</span>
        </button>
        {version && (
          <span className="rounded-full border border-line px-[9px] py-[3px] font-mono text-[11.5px] leading-none whitespace-nowrap text-muted max-sm:hidden">
            판 {version.slice(0, 8)}
          </span>
        )}
      </div>
      {s && (
        <div className="flex items-center gap-2" role="status">
          <span className={`size-[7px] shrink-0 rounded-full ${s.dot}`} />
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
        <p className="text-[13px] leading-normal font-semibold text-[#422c02]">오늘은 새 답변이 쉬어요. 예시 질문과 출처 원문은 그대로 볼 수 있어요.</p>
      </div>
    )
  }
  if (server === 'off') {
    return (
      <div className="shrink-0 border-b border-danger bg-danger px-6 py-[10px]">
        <p className="text-[13px] leading-normal font-semibold text-[#1f0406]">지금은 새 질문을 받지 않아요. 예시 질문과 출처 원문은 그대로 볼 수 있어요.</p>
      </div>
    )
  }
  return null
}
