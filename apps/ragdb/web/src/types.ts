// 질의 서버와 스냅샷 파일의 모양. 정본은 apps/ragdb/app/pipeline.py 와 scripts/snapshot.py 다.
// 여기와 거기가 어긋나면 서버 쪽이 맞다 (RAG/docs/API_계약_초안.md).

export type Kind = '포럼' | '텔레그램' | '랜섬웨어' | '행위자' | '사고' | '판정'

export type DateLabel = '확인일' | '공표 시점' | '수집일' | '검증일'

export interface Source {
  n: number
  chunk_id: string
  document_id: string
  kind: Kind
  title: string
  section: string
  observed_at: string | null
  date_label: DateLabel
  status: string | null
}

export interface Sentence {
  text: string
  sources: number[]
  cited: boolean
}

export type DoneKind = 'prepared' | 'reused' | 'new' | 'no_evidence'

export interface Done {
  kind: DoneKind
  sentences: Sentence[]
  created_at?: string
  version: string
  pii_masked: boolean
  rerank_applied?: boolean
  truncated?: boolean
}

export interface ApiError {
  status: 400 | 401 | 405 | 429 | 503
  code: string
  retry_after?: number
}

export type AskEvent =
  | { event: 'received'; data: Record<string, never> }
  | { event: 'searching'; data: Record<string, never> }
  | { event: 'text'; data: string }
  | { event: 'replace'; data: string }
  | { event: 'sources'; data: Source[] }
  | { event: 'done'; data: Done }
  | { event: 'error'; data: ApiError }

export interface Status {
  ok: boolean
  version: string | null
  accepting: boolean
  reason: 'budget' | 'upstream' | 'no_version' | null
  turnstile: boolean
  budget: { spent_usd: number | null; limit_usd: number }
}

// 스냅샷 (scripts/snapshot.py)
export interface Current {
  version: string
  baked_at: string
}

export interface Chunk {
  chunk_id: string
  section: string
  body: string
  observed_at: string | null
  status: string | null
  images: never[]
}

export interface Doc {
  document_id: string
  kind: Kind
  title: string
  summary: string | null
  status: string | null
  observed_at: string | null
  country: string | null
  signup: boolean | null
  verdict: string | null
  stale: boolean
  attributes: Record<string, string | string[]>
  related: unknown
  chunks: Chunk[]
}

export interface PreparedAnswer {
  question: string
  answer: Sentence[]
  sources: Source[]
  created_at: string
}

export interface Answers {
  version: string
  answers: PreparedAnswer[]
}

export interface SnapshotStatus {
  version: string
  baked_at: string
  documents: number
  chunks: number
}
