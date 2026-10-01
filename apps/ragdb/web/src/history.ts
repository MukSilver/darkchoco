// 지난 질문. 이 탭에서 끝난 답을 브라우저(sessionStorage)에 둔다. 새로 고쳐도 남고, 탭을 닫으면 사라진다.
// 서버로 보내지 않는다. 다시 눌러도 질의 서버를 부르지 않고 그때 받은 답을 그대로 보여 준다.
import { useCallback, useState } from 'react'
import type { Turn } from './useAsk'

export interface Past {
  at: number                // 답을 받은 때 (ms)
  version: string | null    // 그 답을 받을 때의 판
  turn: Turn
}

const KEY = 'ragdb.history.v1'
const OPEN_KEY = 'ragdb.history.open'
const MAX = 20

function read<T>(key: string, fallback: T): T {
  try {
    const raw = sessionStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback        // 저장소를 못 쓰는 브라우저. 기억 없이 그대로 돈다
  }
}

function write(key: string, value: unknown) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value))
  } catch { /* 저장소가 막혔거나 가득 참 */ }
}

export function useHistory() {
  const [list, setList] = useState<Past[]>(() => read<Past[]>(KEY, []))
  const [open, setOpenState] = useState<boolean>(() => read<boolean>(OPEN_KEY, true))

  /** 끝난 답을 맨 위에 넣는다. 같은 답(id)은 다시 넣지 않고, 같은 질문의 옛 답은 새 답으로 바꾼다. */
  const add = useCallback((turn: Turn, version: string | null) => {
    setList((old) => {
      if (old.some((p) => p.turn.id === turn.id)) return old
      const next = [{ at: Date.now(), version, turn }, ...old.filter((p) => p.turn.question !== turn.question)].slice(0, MAX)
      write(KEY, next)
      return next
    })
  }, [])

  const clear = useCallback(() => {
    setList([])
    write(KEY, [])
  }, [])

  const setOpen = useCallback((v: boolean) => {
    setOpenState(v)
    write(OPEN_KEY, v)
  }, [])

  return { list, add, clear, open, setOpen }
}
