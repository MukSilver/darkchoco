// 질의 서버와 스냅샷을 읽는 함수. 화면 컴포넌트는 fetch 를 직접 부르지 않는다.
import type { Answers, AskEvent, Current, Doc, Kind, SnapshotStatus, Status } from './types'

const API = import.meta.env.VITE_API_BASE ?? ''        // 배포: https://rag-api.도메인. 개발: 빈 값 (vite proxy)
const DATA = import.meta.env.VITE_DATA_BASE ?? '/data' // 스냅샷 자리

async function json<T>(url: string): Promise<T> {
  const r = await fetch(url, { cache: 'no-store' })
  if (!r.ok) throw new Error(`${url} ${r.status}`)
  return (await r.json()) as T
}

export const snapshot = {
  current: () => json<Current>(`${DATA}/current.json`),
  status: (version: string) => json<SnapshotStatus>(`${DATA}/${version}/status.json`),
  answers: (version: string) => json<Answers>(`${DATA}/${version}/answers.json`),
  doc: (version: string, documentId: string) =>
    json<Doc>(`${DATA}/${version}/doc/${encodeURIComponent(documentId)}.json`),
}

/** 질의 서버가 살아 있는지. 응답이 없으면 null (화면은 「서버 꺼짐」 상태로). */
export async function serverStatus(): Promise<Status | null> {
  try {
    const r = await fetch(`${API}/api/status`, { cache: 'no-store' })
    return (await r.json()) as Status
  } catch {
    return null
  }
}

/**
 * 새 질문. SSE 이벤트를 차례로 넘긴다 (설계서 「API와 스냅샷 파일」: 받음, 찾는 중, 글자, 바꿈, 출처, 끝, 오류).
 * 스트림이 열리기 전의 오류(400, 401)는 error 이벤트 하나로 바꿔 넘긴다.
 */
export async function ask(
  question: string,
  turnstile: string | null,
  onEvent: (e: AskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch(`${API}/api/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, turnstile }),
    signal,
  })
  if (!r.ok || !r.body) {
    let data = { status: r.status, code: 'http' }
    try { data = await r.json() } catch { /* 본문 없음 */ }
    onEvent({ event: 'error', data } as AskEvent)
    return
  }
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let cut: number
    while ((cut = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, cut)
      buf = buf.slice(cut + 2)
      const e = parseBlock(block)
      if (e) onEvent(e)
    }
  }
}

function parseBlock(block: string): AskEvent | null {
  let event: string | null = null
  let data: string | null = null
  for (const line of block.split('\n')) {
    if (line.startsWith(':')) continue                 // keepalive 주석
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data = (data ?? '') + line.slice(5).trim()
  }
  if (!event) return null
  return { event, data: data ? JSON.parse(data) : {} } as AskEvent
}

/** 그 조각에 붙은 날짜의 이름. 서버(app/answer.py date_label)와 같은 규칙을 둔다. 어긋나면 서버가 맞다. */
export function dateLabel(kind: Kind, documentId: string): '확인일' | '공표 시점' | '수집일' | '검증일' {
  if (kind === '사고') return documentId.includes('-inc-') ? '공표 시점' : '수집일'
  if (kind === '판정') return '검증일'
  return '확인일'
}

/** 사고 문서의 사건 번호 (다른 사이트 링크에 쓴다). 「사고-leak-11」 → LEAK-11 */
export function caseId(documentId: string): string | null {
  const m = /^사고-(leak|inc)-(\d+)$/.exec(documentId)
  return m ? `${m[1].toUpperCase()}-${m[2]}` : null
}
