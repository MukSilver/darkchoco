// 질문 입력 (피그마 「질문 입력 (첫 화면)」 6:74, 「질문 입력 (답 화면)」 6:97).
// 300자 상한. 넘으면 테두리와 글자 수가 빨강. 포커스면 테두리 파랑. Enter 로 보냄, Shift+Enter 줄바꿈.
// 서버 꺼짐과 하루 차단기면 잠기고 안내 문구가 든다.
import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import { QUESTION_MAX } from '../lib/labels'
import type { ServerState } from './Header'

const LOCKED_HOME: Partial<Record<ServerState, string>> = {
  budget: '오늘은 새 답변이 쉬어요. 예시 질문을 눌러 보세요.',
  off: '지금은 새 질문을 받지 않아요. 예시 질문은 볼 수 있어요.',
}
const LOCKED_ANSWER: Partial<Record<ServerState, string>> = {
  budget: '오늘은 새 답변이 쉬어요',
  off: '지금은 새 질문을 받지 않아요',
}

function useBox(onSubmit: (q: string) => void, locked: boolean, busy: boolean) {
  const [value, setValue] = useState('')
  const count = value.length
  const over = count > QUESTION_MAX
  const ready = !locked && !busy && !over && value.trim().length > 0
  const submit = () => {
    if (!ready) return
    onSubmit(value.trim())
    setValue('')
  }
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }
  return { value, setValue, count, over, ready, submit, onKeyDown }
}

function SendButton({ ready, onClick }: { ready: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!ready}
      className={`shrink-0 rounded-[9px] bg-accent px-4 py-[9px] text-[14px] leading-none font-medium whitespace-nowrap text-white ${ready ? 'cursor-pointer hover:brightness-110' : 'opacity-35'}`}
    >
      물어보기
    </button>
  )
}

export function AskBoxHome({ server, onSubmit }: { server: ServerState; onSubmit: (q: string) => void }) {
  const lockedText = LOCKED_HOME[server]
  const locked = !!lockedText
  const b = useBox(onSubmit, locked, false)
  const border = b.over ? 'border-danger' : 'border-line focus-within:border-accent'
  return (
    <div className={`flex w-full flex-col gap-[10px] rounded-[16px] border bg-input px-[18px] pt-4 pb-[14px] transition-colors ${border}`}>
      <textarea
        value={b.value}
        onChange={(e) => b.setValue(e.target.value)}
        onKeyDown={b.onKeyDown}
        disabled={locked}
        rows={3}
        aria-label="질문"
        placeholder={lockedText ?? '예: 2026년 8월에 확인된 텔레그램 채널 중 랜섬웨어 관련은?'}
        className="h-[76px] w-full resize-none bg-transparent text-[17px] leading-[1.5] text-title outline-none placeholder:text-placeholder disabled:cursor-not-allowed"
      />
      <div className="flex items-center justify-between gap-3 border-t border-white/[0.06] pt-3">
        <p className="text-[12.5px] leading-normal text-faint">질문은 저장하지 않아요 · 개인정보는 적지 마세요</p>
        <div className="flex shrink-0 items-center gap-3">
          <span className={`font-mono text-[12px] leading-none ${b.over ? 'text-danger' : 'text-faint'}`}>{b.count}/{QUESTION_MAX}</span>
          <SendButton ready={b.ready} onClick={b.submit} />
        </div>
      </div>
    </div>
  )
}

export function AskBoxAnswer({ server, busy, onSubmit, onExamples }: {
  server: ServerState; busy: boolean; onSubmit: (q: string) => void; onExamples: () => void
}) {
  const lockedText = LOCKED_ANSWER[server]
  const locked = !!lockedText
  const b = useBox(onSubmit, locked, busy)
  const border = b.over ? 'border-danger' : 'border-line focus-within:border-accent'
  return (
    <div className="flex w-full flex-col gap-2">
      <div className={`flex w-full items-end gap-[10px] rounded-[14px] border bg-input py-2 pr-2 pl-4 transition-colors ${border}`}>
        <textarea
          value={b.value}
          onChange={(e) => b.setValue(e.target.value)}
          onKeyDown={b.onKeyDown}
          disabled={locked}
          rows={1}
          aria-label="다른 질문"
          placeholder={lockedText ?? '다른 질문 물어보기'}
          className="max-h-[120px] min-h-[40px] flex-1 resize-none bg-transparent py-2 text-[16px] leading-[1.5] text-title outline-none placeholder:text-placeholder disabled:cursor-not-allowed"
        />
        <span className={`pb-[11px] font-mono text-[12px] leading-none ${b.over ? 'text-danger' : 'text-faint'}`}>{b.count}/{QUESTION_MAX}</span>
        <SendButton ready={b.ready} onClick={b.submit} />
      </div>
      <div className="flex items-start justify-between px-[6px] text-[12.5px] leading-normal">
        <span className="text-faint">질문은 저장하지 않아요</span>
        <button type="button" onClick={onExamples} className="cursor-pointer text-muted hover:text-title">예시 질문</button>
      </div>
    </div>
  )
}
