// 질문 한 건의 화면 상태. 서버 신호(설계서 「API와 스냅샷 파일」)를 받아 단계와 글, 출처를 쥔다.
import { useCallback, useRef, useState } from 'react'
import { ask as askApi } from './api'
import type { ApiError, DoneKind, PreparedAnswer, Sentence, Source } from './types'

export type Phase = 'received' | 'searching' | 'writing' | 'done' | 'error'

export interface Turn {
  id: string                   // 답 한 건의 이름. 지난 질문에 같은 답을 두 번 넣지 않으려고 쓴다
  question: string
  phase: Phase
  text: string                 // 흘러 들어오는 글 (끝나기 전)
  sentences: Sentence[]        // 끝난 뒤의 문장과 출처 번호
  sources: Source[]
  kind: DoneKind | null
  createdAt: string | null     // 사전 답변, 재사용 답변을 만든 시각
  piiMasked: boolean
  truncated: boolean
  error: ApiError | null
  seconds: number | null
}

const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`

const blank = (question: string): Turn => ({
  id: newId(), question, phase: 'received', text: '', sentences: [], sources: [], kind: null, createdAt: null,
  piiMasked: false, truncated: false, error: null, seconds: null,
})

export function useAsk() {
  const [turn, setTurn] = useState<Turn | null>(null)
  const abort = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    abort.current?.abort()
    setTurn(null)
  }, [])

  /** 예시 질문. 스냅샷의 사전 답변을 서버 없이 바로 보여 준다. */
  const showPrepared = useCallback((a: PreparedAnswer) => {
    abort.current?.abort()
    setTurn({
      ...blank(a.question), id: `prepared:${a.question}`, phase: 'done', sentences: a.answer, sources: a.sources, kind: 'prepared',
      createdAt: a.created_at, text: a.answer.map((s) => s.text).join(' '),
    })
  }, [])

  /** 지난 질문. 그때 받은 답을 그대로 다시 보여 준다. 서버를 부르지 않는다. */
  const restore = useCallback((t: Turn) => {
    abort.current?.abort()
    setTurn(t)
  }, [])

  /** 새 질문. */
  const start = useCallback(async (question: string, turnstile: string | null = null) => {
    abort.current?.abort()
    const ctl = new AbortController()
    abort.current = ctl
    const t0 = performance.now()
    setTurn(blank(question))
    const patch = (p: Partial<Turn> | ((t: Turn) => Partial<Turn>)) =>
      setTurn((t) => (t && !ctl.signal.aborted ? { ...t, ...(typeof p === 'function' ? p(t) : p) } : t))
    try {
      await askApi(question, turnstile, (e) => {
        switch (e.event) {
          case 'received': patch({ phase: 'received' }); break
          case 'searching': patch({ phase: 'searching' }); break
          // 글자 토막은 자기 빈칸과 줄바꿈을 달고 온다. 그대로 이어 붙인다 (pipeline.run 과 같음)
          case 'text': patch((t) => ({ phase: 'writing', text: t.text + e.data })); break
          case 'replace': patch({ text: e.data }); break
          case 'sources': patch({ sources: e.data }); break
          case 'done':
            patch({
              phase: 'done', kind: e.data.kind, sentences: e.data.sentences, createdAt: e.data.created_at ?? null,
              piiMasked: e.data.pii_masked, truncated: !!e.data.truncated,
              seconds: Math.round((performance.now() - t0) / 100) / 10,
            })
            break
          case 'error': patch({ phase: 'error', error: e.data }); break
        }
      }, ctl.signal)
      // 끝 신호 없이 스트림이 닫힘
      patch((t) => (t.phase === 'done' || t.phase === 'error' ? {} : { phase: 'error', error: { status: 503, code: 'closed' } }))
    } catch {
      if (!ctl.signal.aborted) patch({ phase: 'error', error: { status: 503, code: 'network' } })
    }
  }, [])

  return { turn, start, showPrepared, restore, reset }
}
