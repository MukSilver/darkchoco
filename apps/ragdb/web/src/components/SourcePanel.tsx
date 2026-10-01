// 출처 원문 (피그마 「UI-03 출처 원문」 12:407, 30:577). 답의 출처 번호를 누르면 그 조각을 보여 준다.
// 머리: 종류, 상태, 날짜와 그 이름, 명칭. 본문: 조각 탭과 조각 글. 속성 조각은 「이름: 값」 줄을 표로 편다.
// 보여 주지 않는 것: 노션 원문 링크, 다크웹 주소, 이미지, 피해 조직 이름 (설계서 「출처 원문」).
import { useEffect, useState } from 'react'
import { dateLabel, snapshot } from '../api'
import { KIND_LABEL } from '../lib/labels'
import { masked } from '../lib/mask'
import type { Chunk, Doc } from '../types'
import { Status } from './Answer'

type Load = { state: 'loading' } | { state: 'missing' } | { state: 'ok'; doc: Doc }

export function useDoc(version: string | null, documentId: string | null): Load {
  const [load, setLoad] = useState<Load>({ state: 'loading' })
  useEffect(() => {
    if (!version || !documentId) return
    let alive = true
    setLoad({ state: 'loading' })
    snapshot.doc(version, documentId)
      .then((doc) => alive && setLoad({ state: 'ok', doc }))
      .catch(() => alive && setLoad({ state: 'missing' }))
    return () => { alive = false }
  }, [version, documentId])
  return load
}

/** 속성 조각인가. 그 줄의 칸 값을 「이름: 값」 으로 편 조각이고 문서의 첫 조각이다 (설계서 「조각」). */
const isAttributes = (doc: Doc, chunk: Chunk) => chunk.section === '속성' && chunk.chunk_id === doc.chunks[0]?.chunk_id

/** 조각의 글. 속성 조각은 문서의 칸 값(attributes)을 표로 편다. 값이 여러 줄이어도 칸 하나로 보인다. */
function ChunkBody({ doc, chunk }: { doc: Doc; chunk: Chunk }) {
  const attrs = Object.entries(doc.attributes ?? {})
  if (isAttributes(doc, chunk) && attrs.length > 0) {
    return (
      <div className="flex w-full flex-col gap-[14px]">
        {doc.summary && (
          <p className="rounded-[12px] border border-line-card bg-input px-4 py-[14px] text-[14px] leading-[1.6] whitespace-pre-line text-title">{masked(doc.summary)}</p>
        )}
        <dl className="flex w-full flex-col border-t border-divider">
          {attrs.map(([k, v]) => (
            <div key={k} className="flex items-start gap-[14px] border-b border-divider py-[11px]">
              <dt className="w-[150px] shrink-0 text-[13px] leading-[1.5] text-muted max-sm:w-[104px]">{k}</dt>
              <dd className="min-w-0 flex-1 text-[13.5px] leading-[1.6] whitespace-pre-line text-body">{masked(Array.isArray(v) ? v.join(' · ') : String(v))}</dd>
            </div>
          ))}
        </dl>
      </div>
    )
  }
  return <p className="text-[15.5px] leading-[1.85] whitespace-pre-line text-body">{masked(chunk.body)}</p>
}

export function DocView({ doc, chunkId, onChunk }: { doc: Doc; chunkId: string | null; onChunk: (id: string) => void }) {
  // 제목만 있고 글이 빈 조각은 탭으로 보이지 않는다 (지금 판에 17개). 속성 조각은 글이 비어도 칸 값을 편다
  const chunks = doc.chunks.filter((c) => c.body.trim() !== '' || isAttributes(doc, c))
  const chunk = chunks.find((c) => c.chunk_id === chunkId) ?? chunks[0]
  const label = dateLabel(doc.kind, doc.document_id)
  return (
    <>
      <div className="flex flex-col gap-[9px]">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-[4px] border border-accent/25 bg-accent/[0.12] px-2 py-[2px] text-[11px] leading-normal font-medium tracking-[0.44px] whitespace-nowrap text-accent-text">
            {KIND_LABEL[doc.kind] ?? doc.kind}
          </span>
          <Status status={chunk?.status ?? doc.status} />
          {(chunk?.observed_at ?? doc.observed_at) && (
            <span className="font-mono text-[12px] leading-none whitespace-nowrap text-muted">{label} {chunk?.observed_at ?? doc.observed_at}</span>
          )}
          {doc.stale && (
            <span className="rounded-[4px] border border-unknown/30 bg-unknown/[0.12] px-2 py-[2px] text-[11px] leading-normal font-medium text-warn-text">오래됨 · 90일 지남</span>
          )}
        </div>
        <h2 className="text-[20px] leading-[1.3] font-semibold tracking-[-0.3px] text-strong">{masked(doc.title)}</h2>
      </div>

      {doc.status === 'offline' && (
        <p className="rounded-[12px] border border-line-card bg-input px-4 py-[14px] text-[13.5px] leading-[1.6] text-muted">
          소멸한 대상이에요. 확인한 날에 접속되지 않아 상태를 offline 으로 바꾸고 기록은 남겨 두었어요.
        </p>
      )}

      {chunks.length > 1 && (
        <div className="flex flex-wrap gap-[6px]" role="tablist" aria-label="같은 문서의 다른 조각">
          {chunks.map((c) => {
            const on = c.chunk_id === chunk?.chunk_id
            return (
              <button
                key={c.chunk_id}
                type="button"
                role="tab"
                aria-selected={on}
                onClick={() => onChunk(c.chunk_id)}
                className={`cursor-pointer rounded-[8px] border px-3 py-[6px] text-[13px] leading-normal font-medium whitespace-nowrap ${
                  on ? 'border-accent/45 bg-accent/[0.18] text-accent-strong' : 'border-line text-muted hover:text-title'
                }`}
              >
                {masked(c.section)}
              </button>
            )
          })}
        </div>
      )}

      {chunk && (
        <div className="flex flex-col gap-[10px]" role="tabpanel">
          <p className="text-[12.5px] leading-normal font-medium text-muted">{masked(chunk.section)}</p>
          <ChunkBody doc={doc} chunk={chunk} />
        </div>
      )}

      <p className="text-[12px] leading-[1.6] text-faint">조직 이름과 주소는 가려져 있어요.</p>
    </>
  )
}

/** 답 옆에 펼치는 패널. 좁은 화면에서는 아래에서 올라오는 시트. */
export function SourcePanel({ version, documentId, chunkId, onChunk, onClose }: {
  version: string; documentId: string; chunkId: string | null; onChunk: (id: string) => void; onClose: () => void
}) {
  const load = useDoc(version, documentId)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <>
    {/* 좁은 화면: 시트 뒤를 어둡게 하고, 누르면 닫는다 */}
    <div className="fixed inset-0 z-10 bg-black/50 lg:hidden" onClick={onClose} aria-hidden="true" />
    <aside
      aria-label="출처 원문"
      className="fixed inset-x-0 bottom-0 z-20 flex max-h-[82vh] flex-col overflow-hidden rounded-t-[16px] border-t border-divider bg-panel lg:static lg:z-auto lg:h-full lg:max-h-none lg:w-[560px] lg:shrink-0 lg:rounded-none lg:border-t-0 lg:border-l"
    >
      <div className="flex shrink-0 items-center justify-between px-6 pt-[22px] pb-[14px]">
        <span className="text-[12px] leading-none font-medium tracking-[1.2px] text-muted">출처 자세히 보기</span>
        <button type="button" onClick={onClose} aria-label="닫기" className="flex size-[30px] cursor-pointer items-center justify-center rounded-[8px] border border-line text-[16px] leading-none text-muted hover:text-title">×</button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-[18px] overflow-y-auto px-6 pb-6">
        {load.state === 'loading' && <p className="text-[13.5px] text-muted">불러오는 중…</p>}
        {load.state === 'missing' && <p className="text-[13.5px] text-muted">찾을 수 없는 문서예요.</p>}
        {load.state === 'ok' && <DocView doc={load.doc} chunkId={chunkId} onChunk={onChunk} />}
      </div>
    </aside>
    </>
  )
}
