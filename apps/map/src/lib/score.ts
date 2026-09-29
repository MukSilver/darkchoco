/**
 * 생태계 지도 계산 규칙 — 설계서 3장 (3.1 ~ 3.12) 을 그대로 옮긴 것.
 *
 * 왜 이 파일만 순수 함수인가
 *   지도·패널·툴팁·검색이 모두 같은 숫자를 써야 한다 (설계서 3.9 「세 곳의 값이
 *   모두 같아야 한다」). 화면마다 제 나름대로 세면 값이 갈라지므로 계산을 여기
 *   한 곳에 모으고, DOM·React·전역 상태를 건드리지 않는다.
 *
 * 왜 Date.now() 가 없는가
 *   설계서 3.1 의 기준일 D 는 「고른 달의 마지막 날」이다. 스냅샷 바로 사용자가
 *   고르는 값이라 현재 시각과 무관하다. 모든 함수가 D 를 인자로 받는다.
 */

/* ────────────────────────────────────────────────────────────────
 * 공용 타입은 types.ts 가 정본이다.
 *
 * 처음에는 여기에 같은 모양으로 임시 선언해 두었고, types.ts 가 생긴
 * 2026-09-22 에 import 로 바꿨다. 한 곳에서만 고치게 하려는 것이다.
 * ──────────────────────────────────────────────────────────────── */

import type {
  Web,
  Island,
  IslandCode,
  Territory,
  Verdict,
  SizeGrade,
  Ev,
  Relation,
} from './types.ts';
import { islandKey as makeIslandKey } from './types.ts';

export type { Web, Island, Territory, Verdict, SizeGrade, Ev, Relation };

/* ────────────────────────────────────────────────────────────────
 * 가중치 (설계서 3.1 단서: ontology_v1.json 의 weights 에서 바꾼다)
 *
 * 설계서 5.2 가 「가중치 값, 규모 등급 기준, 활동도·위험도 계산식」을 전부
 * 「제안값, 팀 확정 필요」로 묶어 두었다. 값이 바뀔 것을 알고 있으므로
 * 코드에 숫자를 박지 않고 설정 객체로 빼고, 모든 함수가 마지막 인자로 받는다.
 * 나중에 ontology_v1.json 을 읽어 이 모양으로 넘기기만 하면 된다.
 * ──────────────────────────────────────────────────────────────── */

export type Weights = {
  /** N(W) — 웹 W 의 전체 칸 수. 정본 800 (가중치!B48) */
  readonly totalCells: Readonly<Record<Web, number>>;
  /** w_신뢰 — 설계서 3.2 */
  readonly trust: Readonly<Record<Verdict, number>>;
  /** w_규모 — 설계서 3.2. 규모 등급 기준 자체도 (제안) 이다 */
  readonly size: Readonly<Record<SizeGrade, number>>;
  /**
   * 기본점 b — 설계서 3.4. 정본 20 (가중치!B51).
   *
   * 영토 점수 = (사건 지수 + b) × w. 사건이 없어도 활동도만큼 크기를 갖는다.
   * 올릴수록 큰 영토와 작은 영토의 차이가 줄어든다.
   */
  readonly base: number;
  /** 활동도 가중치 최솟값. w = 최솟값 + (1 − 최솟값) × 활동도 ÷ 100 (가중치!B52) */
  readonly activityMin: number;
  /**
   * 섬 비중 지수 α (가중치!B53). 섬 몫을 정할 때 섬 점수에 매긴다.
   * 1 이면 점수 그대로라 영토가 많은 랜섬웨어 섬이 지도를 거의 다 차지한다
   */
  readonly islandAlpha: number;
  /** 최근 기간 (일). 30일 건수 · 변화율 · 상태 (가중치!B49) */
  readonly activityWindowDays: number;
  /** 급상승 기간 (일). 설계서 3.8 (가중치!B50) */
  readonly surgeWindowDays: number;
};

export const DEFAULT_WEIGHTS: Weights = Object.freeze({
  // 오픈웹과 다크웹은 따로 계산한다 (설계서 3.5) — 그래서 웹별로 둔다
  totalCells: Object.freeze({ open: 800, dark: 800 }),
  trust: Object.freeze({
    confirmed: 1.0, // 확인됨
    high: 1.0, // 신뢰성 높음
    unverified: 0.8, // 검증 전
    unknown: 0.7, // 미확인
    low: 0.4, // 신뢰성 낮음
    false: 0, // 허위
  }),
  size: Object.freeze({
    large: 1.5, // 큼
    medium: 1.2, // 중간
    small: 1.0, // 작음
    unknown: 1.0, // 모름 — 작음과 같은 1.0 이다 (설계서 3.2)
  }),
  base: 20,
  activityMin: 0.5,
  islandAlpha: 0.6,
  activityWindowDays: 30,
  surgeWindowDays: 7,
});

/** 설계서 3.7 의 상태 값. 화면 표기 그대로 쓴다 */
export type Status = '활성' | '관측 중';

/** 설계서 3.11 의 위험도 등급 (제안) */
export type RiskLevel = '높음' | '중간' | '낮음';

/* ────────────────────────────────────────────────────────────────
 * 숫자 다루기
 * ──────────────────────────────────────────────────────────────── */

const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * 점수 합을 다룰 때 쓰는 자리수.
 *
 * 가중치가 소수 한두 자리라 곱은 최대 소수 셋째 자리까지만 나온다.
 * 그런데 0.7 을 31 번 더하면 부동소수 오차로 33.699999999999996 이 되어
 * 설계서 3.4 실측 표의 33.7 과 눈으로 대조가 안 된다. 의미가 있는 자리보다
 * 훨씬 아래인 6 자리에서 끊어 오차만 걷어낸다. 값 자체는 바뀌지 않는다.
 */
const SCORE_DIGITS = 6;

function roundTo(value: number, digits: number): number {
  const f = 10 ** digits;
  return Math.round(value * f) / f;
}

/**
 * 섬 키. 설계서 2.3 에서 OTHER 코드가 오픈웹·다크웹 양쪽에 있어 web 을 붙여야
 * 유일해진다.
 *
 * **여기서 따로 만들지 않고 `types.ts` 것을 부른다.** 2026-09-22 까지는 이 파일이
 * `${web}::${islandId}` 를 따로 만들었는데, `types.ts` 는 콜론 하나짜리
 * `${web}:${id}` 를 냈고 인자 순서까지 반대였다. `islands.ts` 의 조회 표가
 * `types.ts` 쪽 키로 만들어져 있어서, 한쪽에서 만든 키로 다른 쪽을 찾으면
 * 값이 조용히 안 맞았다. 인자 순서는 이 파일의 부르는 자리를 안 고치려고
 * 그대로 두었다.
 */
export function islandKey(islandId: string, web: Web): string {
  return makeIslandKey(web, islandId as IslandCode);
}

/**
 * 달의 마지막 날 끝.
 *
 * **기준일 D 는 판 1.2 에서 분기로 바뀌었다** (`endOfQuarterUTC`). 이 함수는
 * 월별 막대처럼 달 단위가 남아 있는 자리와 시험에서 쓴다.
 *
 * 그날 올라온 사건까지 포함해야 하므로 그 날의 끝(23:59:59.999)을 돌려준다.
 * 날짜만 있는 ISO 문자열은 UTC 자정으로 해석되는데, 그것을 D 로 쓰면 그날
 * 낮에 올라온 사건이 통째로 빠진다. 수집 시각이 UTC 로 저장되므로 UTC 로 맞춘다.
 */
export function endOfMonthUTC(year: number, month1to12: number): Date {
  return new Date(Date.UTC(year, month1to12, 0, 23, 59, 59, 999));
}

/** 분기(1~4)의 마지막 달. Q1→3월, Q2→6월, Q3→9월, Q4→12월 */
export function quarterEndMonth(q: number): number {
  return q * 3;
}

/** 어느 분기인가. 1~12월 → 1~4 */
export function quarterOf(month1to12: number): number {
  return Math.ceil(month1to12 / 3);
}

/**
 * 기준일 D — 「고른 분기의 마지막 날, 이번 분기는 오늘」 (설계서 3.1, 판 1.2).
 *
 * **이번 분기만 예외인 까닭이 있다.** 분기 마지막 날로 잡으면 아직 오지 않은
 * 날이 최근 7일·30일 창에 들어가 급상승과 30일 변화율이 비어 버린다.
 * 설계서가 그 한 줄을 따로 적어 두었다.
 *
 * **`today` 를 인자로 받는다.** 이 파일은 `Date.now()` 를 안 쓴다 — 기준일이
 * 현재 시각에 매이면 같은 입력이 같은 지도를 안 낸다. 오늘이 필요한 자리는
 * 화면이 넘겨 준다. 안 넘기면 분기 끝을 그대로 쓴다.
 */
export function endOfQuarterUTC(
  year: number,
  q: number,
  today?: Date,
): Date {
  const end = new Date(
    Date.UTC(year, quarterEndMonth(q), 0, 23, 59, 59, 999),
  );
  if (!today) return end;
  // 오늘이 그 분기 안이면 오늘 끝까지만 본다
  return today.getTime() < end.getTime()
    ? new Date(
        Date.UTC(
          today.getUTCFullYear(),
          today.getUTCMonth(),
          today.getUTCDate(),
          23,
          59,
          59,
          999,
        ),
      )
    : end;
}

/** D 에서 며칠 뺀 시점. 30일 변화·급상승 폭이 쓴다 (설계서 3.6·3.8) */
export function minusDays(d: Date, days: number): Date {
  return new Date(d.getTime() - days * DAY_MS);
}

/* ────────────────────────────────────────────────────────────────
 * 3.2 사건 점수
 * ──────────────────────────────────────────────────────────────── */

/**
 * s(e) = 1 × w_신뢰(e) × w_규모(e)  — 설계서 3.2 (판 1.2)
 *
 * 앞의 1 은 설계서에 적힌 대로 남겨 둔다. 사건 1건의 기본값이 1점이라는
 * 뜻이고, 곱만 보면 사라져 보이지만 나중에 기본값을 손댈 자리다.
 *
 * **중복 가중치가 없어졌다.** 판 1.1 은 재게시를 0.5배로 깎았는데 판 1.2 가
 * 「재게시와 같은 글도 1점. 중복 가중치를 두지 않음 (판 1.1의 0.5점 삭제)」로
 * 바꿨다. `Ev.repost` 칸은 그대로 둔다 — 점수에는 안 쓰지만 사건 종류 칩에
 * 「재게시」를 띄우는 데 쓴다 (설계서 2.3).
 */
export function eventScore(e: Ev, w: Weights = DEFAULT_WEIGHTS): number {
  return roundTo(1 * w.trust[e.verdict] * w.size[e.size], SCORE_DIGITS);
}

/* ────────────────────────────────────────────────────────────────
 * 3.1 E(T, D) — 집계에 드는 사건
 * ──────────────────────────────────────────────────────────────── */

/**
 * E(T,D) 의 조건: D 이전 게시 · 반출 제외 아님 · 허위 아님 (설계서 3.1)
 *
 * 허위를 여기서도 빼는 이유는 점수뿐 아니라 건수 C(T,D) 에서도 빠져야 하기
 * 때문이다. 가중치 0 만으로는 3.7 의 사건 수가 허위까지 세게 된다.
 * 게시 시각이 없거나 깨진 사건은 지도에 올리지 않는다 (설계서 2.1).
 */
export function inScope(e: Ev, d: Date): boolean {
  if (e.excluded) return false;
  if (e.verdict === 'false') return false;
  const t = Date.parse(e.postedAt);
  if (Number.isNaN(t)) return false;
  return t <= d.getTime();
}

/* ────────────────────────────────────────────────────────────────
 * 정본 계산 — 3.3 활동도 · 3.4 영토 점수 · 3.5 칸 수 · 3.6 비중 ·
 *             3.7 사건 수와 상태 · 3.8 급상승
 *
 * **정본은 온톨로지판 엑셀과 설계서 PDF 63쪽이다** (2026-09-23 최현서).
 * PDF 글과 엑셀 수식이 어긋나면 엑셀을 따른다 — 엑셀이 3.5 실측 표를 한 칸도
 * 안 틀리게 재현한다. 칸 주소는 그 엑셀의 영토 탭 · 섬 탭 · 영토분기별 탭이다.
 *
 * 흐름은 엑셀 탭과 같다.
 *
 *   사건 점수 합 I  →  사건 지수 J  ─┐
 *   활동도 원자료 R →  활동도 S → w T ┴→  영토 점수 U = (J + b) × T
 *   섬 점수 Σ U  →  섬 칸 목표 L (섬 비중 지수 α)  →  섬 안에서 칸 수 AA
 *
 * **판 1.2 md 와 셋이 다르다.** 사건 점수 합을 그대로 쓰지 않고 섬 안에서
 * 0~100 으로 누른 사건 지수를 쓴다. 기본점이 1 에서 20 으로, 전체 칸이 400 에서
 * 800 으로 늘었다. 칸을 웹 전체에서 한 번에 나누지 않고 섬 몫부터 정한다.
 * ──────────────────────────────────────────────────────────────── */

/**
 * 엑셀 ROUND. **0.5 를 0 에서 먼 쪽으로 올린다.**
 *
 * 엑셀은 소수 표기(15자리 안팎) 그대로 반올림한다. 부동소수를 그대로 곱해
 * 반올림하면 62.5 가 62.49999… 로 읽혀 한 칸씩 어긋난다. 숫자를 가장 짧은
 * 소수 표기로 바꾼 뒤 지수 표기로 자리를 옮겨 반올림한다 — 파이썬
 * `Decimal(repr(x)).quantize(ROUND_HALF_UP)` 와 같은 일이고, 그 방식으로
 * 엑셀 캐시 178곳 · 543줄이 모두 맞았다.
 */
export function excelRound(x: number, digits = 0): number {
  if (!Number.isFinite(x)) return x;
  const sign = x < 0 ? -1 : 1;
  const [m, e] = Math.abs(x).toExponential().split('e');
  const shifted = Number(`${m}e${Number(e) + digits}`);
  const r = Math.round(shifted); // shifted ≥ 0 이라 half-up 이 곧 0 에서 먼 쪽
  return sign * Number(`${r}e${-digits}`);
}

/**
 * 로그 지수 = round(100 × ln(1+x) ÷ ln(1+섬 최댓값)) — 설계서 3.3 · 3.4.
 *
 * 활동도와 사건 지수가 같은 모양이다. 로그를 써서 100배 차이가 나도 노드가
 * 100배 커지지 않게 한다. 최댓값이 0 이면 0 이다 (엑셀 IFERROR).
 */
export function logIndex(x: number, max: number): number {
  if (!(max > 0) || !(x > 0)) return 0;
  return excelRound((100 * Math.log(1 + x)) / Math.log(1 + max));
}

/** 숫자로 쓸 수 있는 원자료만. 빈칸 · 글자 · 음수는 없는 것으로 본다 */
function rawNum(v: number | null | undefined): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/**
 * 포럼 활동도 — 회원 · 게시물 · 스레드 지수의 평균 (설계서 3.3, 영토!O~S).
 *
 * **빈 지수는 빼고 평균한다.** 0 이거나 없는 칸은 0 으로 넣지 않는다 —
 * 엑셀 AVERAGE 가 빈 문자열을 건너뛴다. 회원 90 · 게시물 72 · 스레드 없음이면
 * 81 이지 54 가 아니다. 반올림은 두 번이다. 지수마다 한 번, 평균에 한 번.
 *
 * 최댓값은 포럼 영토 전부에서 칸마다 따로 잡는다. 사건이 없는 포럼도 들어간다.
 */
export function forumActivity(
  t: Pick<Territory, 'raw' | 'posts' | 'threads'>,
  max: { raw: number; posts: number; threads: number },
): number {
  const parts: number[] = [];
  for (const k of ['raw', 'posts', 'threads'] as const) {
    const v = rawNum(t[k]);
    if (v === null || v <= 0) continue;
    parts.push(logIndex(v, max[k]));
  }
  if (parts.length === 0) return 0;
  return excelRound(parts.reduce((a, b) => a + b, 0) / parts.length);
}

/** w(활동도) = 최솟값 + (1 − 최솟값) × 활동도 ÷ 100 — 설계서 3.3 (0.5 ~ 1.0) */
export function activityWeight(activity: number, w: Weights = DEFAULT_WEIGHTS): number {
  return w.activityMin + ((1 - w.activityMin) * activity) / 100;
}

/**
 * 섬 칸 목표 N(I) = round(N(W) × S(I)^α ÷ Σ S(I′)^α) — 설계서 3.5 (섬!J~L).
 *
 * **합이 N(W) 에서 어긋나면 조정 점수가 가장 큰 섬에 끝전을 준다.** PDF 는 이
 * 규칙을 안 적었지만 엑셀에 있다 (섬!L). 2026-Q1 에 합이 799 가 되어
 * 랜섬웨어가 1칸을 더 받았다. 가장 큰 섬이 여럿이면 목록에서 앞선 섬이다.
 *
 * `order` 는 섬 키 차례다. 점수가 0 인 섬도 넣어야 0칸을 받는다.
 */
export function islandTargets(
  order: readonly string[],
  scores: ReadonlyMap<string, number>,
  total: number,
  alpha: number,
): Map<string, number> {
  const adj = order.map((k) => {
    const s = scores.get(k) ?? 0;
    return s > 0 ? s ** alpha : 0;
  });
  const sum = adj.reduce((a, b) => a + b, 0);
  const out = new Map<string, number>();
  if (!(sum > 0)) {
    for (const k of order) out.set(k, 0);
    return out;
  }
  const raw = adj.map((a) => excelRound((total * a) / sum));
  const diff = total - raw.reduce((a, b) => a + b, 0);
  let top = 0;
  for (let i = 1; i < adj.length; i++) if (adj[i] > adj[top]) top = i;
  order.forEach((k, i) => out.set(k, raw[i] + (i === top ? diff : 0)));
  return out;
}

/**
 * 섬 안에서 영토로 칸을 나눈다 — 설계서 3.5 (영토!V~AA).
 *
 *   x  = 섬 안 비중 × 섬 칸 목표
 *   X  = max(1, 정수 부분(round(x, 6)))       0칸이면 1칸으로 올린다
 *   Y  = x − X                               나머지
 *   남는 칸 d = 섬 칸 목표 − ΣX
 *   d ≥ 0 이면 나머지 큰 순으로 d 곳에 1칸씩
 *   d < 0 이면 2칸 이상인 곳 가운데 나머지 작은 순으로 −d 곳에서 1칸씩 뺀다
 *
 * **나머지가 같으면 목록에서 앞선 영토가 먼저다** (엑셀은 영토 번호 순).
 * 계산 순서를 엑셀과 똑같이 둔다 — 비중 → x → 나머지. 나머지를 반올림하지
 * 않고 그대로 견준다. 같은 점수의 영토가 같은 비트의 나머지를 가져야 동점이
 * 엑셀과 똑같이 갈린다.
 */
export function allocateCells(
  scores: readonly number[],
  target: number,
): { cells: number[]; floor: number[]; rest: number[] } {
  const sum = scores.reduce((a, b) => a + b, 0);
  const x = scores.map((u) => (sum > 0 ? u / sum : 0) * target);
  const floor = x.map((v) => Math.max(1, Math.floor(excelRound(v, 6))));
  const rest = x.map((v, i) => v - floor[i]);
  const d = target - floor.reduce((a, b) => a + b, 0);
  const cells = floor.map((f, i) => {
    if (d >= 0) {
      let rank = 1;
      for (let j = 0; j < rest.length; j++) {
        if (rest[j] > rest[i] || (rest[j] === rest[i] && j < i)) rank += 1;
      }
      return f + (rank <= d ? 1 : 0);
    }
    if (f <= 1) return f;
    let rank = 1;
    for (let j = 0; j < rest.length; j++) {
      if (floor[j] <= 1) continue;
      if (rest[j] < rest[i] || (rest[j] === rest[i] && j < i)) rank += 1;
    }
    return f - (rank <= -d ? 1 : 0);
  });
  return { cells, floor, rest };
}

/** 분기의 첫날 0시 (UTC) */
function quarterStartUTC(d: Date): Date {
  return new Date(Date.UTC(d.getUTCFullYear(), Math.floor(d.getUTCMonth() / 3) * 3, 1));
}

/**
 * 영토가 기준일 D 에 지도에 있는가 (작업판 영토분기별 탭의 줄 규칙).
 *
 * `since`(가장 이른 사건) 가 D 이전이면 있다. 사건이 없는 명부 영토는 이번
 * 분기에만 있다 — 명부에 오른 날을 모르니 지난 분기에 넣지 않는다.
 * `today` 를 모르면 `since` 가 없는 영토를 늘 있는 것으로 본다.
 *
 * `until`(운영 종료 날짜) 이 있으면 그 날짜가 든 분기까지만 있다. D 가 든 분기가
 * 그 날 뒤에 시작하면 없다 (2026-09-30 최현서 — 압수된 곳은 압수 전 분기에만).
 */
export function presentAt(t: Territory, d: Date, today?: Date): boolean {
  if (t.until) {
    const u = Date.parse(t.until);
    if (!Number.isNaN(u) && quarterStartUTC(d).getTime() > u) return false;
  }
  if (t.since) {
    const s = Date.parse(t.since);
    if (!Number.isNaN(s)) {
      if (s <= d.getTime()) return true;
      if (!today) return false;
    }
  }
  if (!today) return true;
  return d.getTime() >= quarterStartUTC(today).getTime();
}

/** 창 안에 드는지. 왼쪽은 열고 오른쪽은 닫는다 — t(e) > D − k일, t(e) ≤ D */
function inWindow(e: Ev, from: Date, to: Date): boolean {
  const t = Date.parse(e.postedAt);
  if (Number.isNaN(t)) return false;
  return t > from.getTime() && t <= to.getTime();
}

/** 영토 T 의 E(T,D). 입력 순서를 그대로 지켜 결과가 항상 같게 한다 */
export function scopedEvents(events: readonly Ev[], territoryId: string, d: Date): Ev[] {
  return events.filter(
    (e) => (e.territoryId === territoryId || e.actorTerritoryId === territoryId) && inScope(e, d),
  );
}

/**
 * 급상승 폭이 큰 영토 (설계서 3.8). 검색 화면이 3곳을 쓴다.
 *
 * 사건이 없거나 폭이 0 이하인 곳은 순위에 안 넣는다 (영토!AK).
 * 동점이면 입력 순서를 지킨다.
 */
export function topSurges(result: MapResult, limit = 3): { territoryId: string; surge: number }[] {
  return result.territories
    .map((m, i) => ({ m, i }))
    .filter(({ m }) => m.eventCount > 0 && m.surge7d > 0)
    .sort((a, b) => b.m.surge7d - a.m.surge7d || a.i - b.i)
    .slice(0, limit)
    .map(({ m }) => ({ territoryId: m.territoryId, surge: m.surge7d }));
}

/* ────────────────────────────────────────────────────────────────
 * 3.9 관계 건수
 * ──────────────────────────────────────────────────────────────── */

/**
 * 관계 R 의 근거 사건 가운데 기준일 D 에 지도에 든 것 — E(R,D) (설계서 3.9).
 * 관계 탭 근거 목록(4.3.6 ⑦-8e)이 이 목록을 그대로 보인다
 */
export function evidenceInScope(relation: Relation, events: readonly Ev[], d: Date): Ev[] {
  const byId = new Map(events.map((e) => [e.id, e]));
  const out: Ev[] = [];
  for (const id of relation.evidence) {
    const e = byId.get(id);
    if (e && inScope(e, d)) out.push(e);
  }
  return out;
}

/**
 * n(R) = |E(R,D)| — 설계서 3.9
 * E(R,D): 관계 R 의 근거 사건 중 D 이전 게시, 허위·반출 제외가 아닌 것
 *
 * 설계서가 「[연결] 탭 행, 관계선 라벨, 관계 연혁에서 모두 같은 값이어야 한다」고
 * 못 박았다. 그래서 세 화면이 각자 세지 말고 이 함수만 부르게 한다.
 *
 * 노션 「근거 사건 수」 칸을 안 쓴다. 작업판도 이 값을 수식으로 센다.
 *
 * **0 과 1 을 가른다.**
 *   - 근거가 처음부터 없으면 1 — 「연결된 곳」 칸에서 만든 관계선이다 (3.9).
 *     화면에 「0건」이 찍히면 관계가 없는 것처럼 보인다
 *   - 근거가 있는데 D 에 하나도 안 들면 0 — 그 분기에는 아직 없던 관계다.
 *     `islandPair` 와 화면은 0 인 관계선을 안 그린다
 *
 * 노션 「지도 가중치」 DB 는 「근거 사건이 없는 관계는 0이고 선은 그대로
 * 그림」이라 적어 앞의 경우와 어긋난다. 설계서 PDF 와 작업판을 따랐다.
 */
export function relationCount(relation: Relation, events: readonly Ev[], d: Date): number {
  if (relation.evidence.length === 0) return 1;
  return evidenceInScope(relation, events, d).length;
}

/**
 * 관계를 처음 본 날과 마지막 본 날 — 설계서 4.3.6 관계 연혁.
 *
 * 근거 사건 가운데 D 에 지도에 든 것의 가장 이른·늦은 게시 시각이다.
 * 작업판 관계선후보 탭 수식(`AGGREGATE(15/14, …)`)과 같다. 노션 칸은 25줄
 * 모두 비어 있고, 비어 있는 것이 맞다 — 코드가 세는 값이다.
 * 근거가 없거나 D 에 하나도 안 들면 둘 다 null 이다.
 */
export function relationSpan(
  relation: Relation,
  events: readonly Ev[],
  d: Date,
): { first: string | null; last: string | null } {
  let first: string | null = null;
  let last: string | null = null;
  let lo = Infinity;
  let hi = -Infinity;
  for (const e of evidenceInScope(relation, events, d)) {
    const t = Date.parse(e.postedAt);
    if (t < lo) {
      lo = t;
      first = e.postedAt;
    }
    if (t > hi) {
      hi = t;
      last = e.postedAt;
    }
  }
  return { first, last };
}

/**
 * N(A → B) = Σ_{R: from ∈ A, to ∈ B} n(R)  — 설계서 3.9
 * 엔티티 쌍 수는 그 관계의 개수다 (근거 건수가 아니다).
 * D 에 아직 없던 관계(n(R) = 0)는 쌍 수에도 안 넣는다.
 */
export function islandPair(
  relations: readonly Relation[],
  territories: readonly Territory[],
  events: readonly Ev[],
  d: Date,
  fromIslandKey: string,
  toIslandKey: string,
): { pairs: number; count: number } {
  const keyOf = new Map(territories.map((t) => [t.id, islandKey(t.islandId, t.web)]));
  let pairs = 0;
  let count = 0;
  for (const r of relations) {
    if (keyOf.get(r.from) !== fromIslandKey) continue;
    if (keyOf.get(r.to) !== toIslandKey) continue;
    const n = relationCount(r, events, d);
    if (n === 0) continue;
    pairs += 1;
    count += n;
  }
  return { pairs, count };
}

/*
 * 3.10 활동도 영향은 **판 1.2 에서 절이 통째로 없어졌다.**
 *
 * 사건 하나를 빼고 활동도를 다시 세어 차를 보는 계산이었는데, 판 1.2 에서
 * 활동도가 사건과 무관해졌다 — 회원 수·구독자 수 같은 규모 원자료로 낸다.
 * 사건을 빼도 값이 안 움직이므로 계산 자체가 뜻을 잃었다. 설계서 5.3 도
 * 「⑦-5 정보 표에서 활동도 영향 삭제」로 적었다.
 */

/* ────────────────────────────────────────────────────────────────
 * 3.11 위험도 (제안)
 * ──────────────────────────────────────────────────────────────── */

/**
 * 위험도의 입력.
 *
 * 공용 Ev 에 없는 값이라 따로 받는다. 설계서 3.11 이 「즉시 악용 가능성」과
 * 「유출 항목」 두 가지를 조건으로 쓰는데 둘 다 수집 DB 칸이고 아직 Ev 에
 * 올라와 있지 않다. Ev 가 이 칸들을 갖게 되면 이 타입은 지운다.
 */
export type RiskFacts = {
  /** 수집 DB '즉시 악용 가능성' — 가능 / 조건부 / 그밖 */
  immediateAbuse: 'possible' | 'conditional' | 'none';
  /** 유출 항목에 주민번호가 있는가 */
  hasResidentId: boolean;
  /** 유출 항목에 카드·금융 정보가 있는가 */
  hasCardFinance: boolean;
};

/**
 * 위험도 (설계서 3.11, 제안)
 *   높음  즉시 악용 가능성 '가능', 또는 유출 항목에 주민번호·카드금융 포함
 *   중간  즉시 악용 가능성 '조건부'
 *   낮음  그밖
 *
 * 순서가 중요하다. '조건부'라도 주민번호가 들어 있으면 높음이다.
 * 설계서가 높음 줄에 '또는'을 썼으므로 높음을 먼저 본다.
 */
export function riskLevel(facts: RiskFacts): RiskLevel {
  if (facts.immediateAbuse === 'possible' || facts.hasResidentId || facts.hasCardFinance) return '높음';
  if (facts.immediateAbuse === 'conditional') return '중간';
  return '낮음';
}

/* ────────────────────────────────────────────────────────────────
 * 한 번에 계산하기
 * ──────────────────────────────────────────────────────────────── */

export type TerritoryMetrics = {
  territoryId: string;
  islandKey: string;
  web: Web;
  /** 기준일에 지도에 있는가. 없으면 칸도 점수도 0 이다 (`presentAt`) */
  present: boolean;
  /** 3.4 영토 점수 S(T,D) = (사건 지수 + b) × w (영토!U) */
  score: number;
  /** 사건 점수 합 Σ s(e) (영토!I) */
  eventScoreSum: number;
  /** 사건 지수, 0~100 (영토!J) */
  eventIndex: number;
  /** 3.5 칸 수 n(T) (영토!AA) */
  cells: number;
  /** 3.6 섬 안 비중, % (영토!V × 100) */
  shareInIsland: number;
  /** 웹 전체 대비 비중, % (영토!W × 100) */
  shareInWeb: number;
  /** 3.3 활동도, 0~100 (영토!S) */
  activity: number;
  /** 3.3 w(활동도), 0.5~1.0 (영토!T) */
  activityWeight: number;
  /** 3.8 급상승 폭 = 최근 7일 점수 − 직전 7일 점수 (영토!AH) */
  surge7d: number;
  /** 3.7 C(T,D) (영토!H). 행위자 영토는 그 행위자가 올린 사건 수다 */
  eventCount: number;
  /** 최근 30일 · 직전 30일 건수 (영토!AB · AC). 날짜를 대신 넣은 사건은 뺀다 */
  recent30: number;
  prev30: number;
  /** 3.7 30일 변화율, %. 직전 30일이 0건이면 null (영토!AD × 100) */
  countChangeRate30d: number | null;
  /** 3.7 */
  status: Status;
  /** 첫 사건 · 마지막 사건 게시 시각 (영토!AL · AM). 사건이 없으면 null */
  firstEventAt: string | null;
  lastEventAt: string | null;
};

export type IslandMetrics = {
  islandKey: string;
  islandId: string;
  web: Web;
  /** 3.4 S(I,D) = 소속 영토 점수의 합 (섬!I) */
  score: number;
  /** 3.5 섬 칸 목표 N(I) (섬!L) */
  target: number;
  /** 3.5 소속 영토 칸 수의 합. 목표와 같다 (섬!M) */
  cells: number;
  /** 3.3 소속 영토 활동도의 평균, 정수 (섬!O) */
  avgActivity: number;
  /** 3.7 소속 영토 사건 합. 행위자 섬은 같은 사건을 한 번 더 센 값이다 (섬!G) */
  eventCount: number;
};

export type MapInput = {
  islands: readonly Island[];
  territories: readonly Territory[];
  events: readonly Ev[];
  /**
   * 오늘. 사건이 없는 명부 영토를 이번 분기에만 싣는 데 쓴다 (`presentAt`).
   * 이 파일은 `Date.now()` 를 안 쓴다 — 화면이 넘겨 준다
   */
  today?: Date;
};

export type MapResult = {
  /** 기준일 D */
  d: Date;
  territories: TerritoryMetrics[];
  islands: IslandMetrics[];
  webScore: Record<Web, number>;
  /** 웹별 칸 수 합. N(W) 와 같다 */
  webCells: Record<Web, number>;
  /**
   * 지도에 든 사건 수. **행위자 섬에서 한 번 더 센 것을 빼고 센다.**
   * 섬 사건 수를 더하면 행위자 몫이 두 번 들어간다 (정본 요약 탭의 217 이
   * 그렇다. 실제 사건은 170 이다)
   */
  eventCount: Record<Web, number>;
};

type Acc = {
  H: number; // 사건 수
  I: number; // 사건 점수 합
  rawCount: number; // 날짜를 대신 넣은 사건을 뺀 사건 수 (행위자 활동도)
  AB: number; // 최근 30일 건수
  AC: number; // 직전 30일 건수
  AF: number; // 최근 7일 점수
  AG: number; // 직전 7일 점수
  first: number;
  last: number;
  firstAt: string | null;
  lastAt: string | null;
};

const ACTOR: IslandCode = 'ACTOR';
const FORUM: IslandCode = 'FORUM';

/**
 * 설계서 3.3 ~ 3.8 을 한 기준일에 대해 한 번에 낸다.
 *
 * 화면마다 따로 부르면 같은 값을 여러 번 세게 되고, 중간에 기준일이 어긋나면
 * 패널과 지도가 다른 숫자를 말한다. 기준일을 한 번만 받아 한 덩어리로 돌려준다.
 * 지난 분기 스냅샷도 이 함수를 그 분기 끝으로 한 번 더 부른다.
 */
export function computeMap(input: MapInput, d: Date, w: Weights = DEFAULT_WEIGHTS): MapResult {
  const { islands, territories, events, today } = input;

  const ids = new Set(territories.map((t) => t.id));
  const actors = new Set(territories.filter((t) => t.islandId === ACTOR).map((t) => t.id));
  const present = new Map(territories.map((t) => [t.id, presentAt(t, d, today)]));

  // ── 사건을 영토에 모은다 (영토!H · I · AB · AC · AF · AG · AL · AM) ──
  const acc = new Map<string, Acc>();
  for (const t of territories) {
    acc.set(t.id, {
      H: 0, I: 0, rawCount: 0, AB: 0, AC: 0, AF: 0, AG: 0,
      first: Infinity, last: -Infinity, firstAt: null, lastAt: null,
    });
  }
  const r30 = minusDays(d, w.activityWindowDays);
  const p30 = minusDays(d, w.activityWindowDays * 2);
  const r7 = minusDays(d, w.surgeWindowDays);
  const p7 = minusDays(d, w.surgeWindowDays * 2);
  const counted = new Set<string>();

  for (const e of events) {
    // 제 영토가 목록에 없는 사건은 어디에도 안 센다 — 행위자 영토에서도.
    // 엑셀에서는 「영토가 지도에서 빠진 곳」 사유로 계산 대상에서 빠진다
    if (!ids.has(e.territoryId)) continue;
    if (!inScope(e, d)) continue;
    const targets = [e.territoryId];
    if (e.actorTerritoryId && e.actorTerritoryId !== e.territoryId && actors.has(e.actorTerritoryId)) {
      targets.push(e.actorTerritoryId);
    }
    const s = eventScore(e, w);
    const t = Date.parse(e.postedAt);
    const real = !e.dateSubstituted;
    for (const id of targets) {
      if (!present.get(id)) continue;
      const a = acc.get(id)!;
      a.H += 1;
      a.I += s;
      counted.add(e.id);
      if (t < a.first) { a.first = t; a.firstAt = e.postedAt; }
      if (t > a.last) { a.last = t; a.lastAt = e.postedAt; }
      // 날짜를 대신 넣은 사건은 창 · 상태 · 변화율 · 급상승 · 행위자 활동도에서 뺀다
      if (!real) continue;
      a.rawCount += 1;
      if (inWindow(e, r30, d)) a.AB += 1;
      else if (inWindow(e, p30, r30)) a.AC += 1;
      if (inWindow(e, r7, d)) a.AF += s;
      else if (inWindow(e, p7, r7)) a.AG += s;
    }
  }

  // ── 섬 차례. 목록의 섬 다음에 영토에만 있는 섬 ──
  const keyOf = (t: Territory) => islandKey(t.islandId, t.web);
  const order: string[] = [];
  for (const i of islands) {
    const k = islandKey(i.id, i.web);
    if (!order.includes(k)) order.push(k);
  }
  for (const t of territories) if (!order.includes(keyOf(t))) order.push(keyOf(t));
  const members = new Map<string, Territory[]>();
  for (const k of order) members.set(k, []);
  for (const t of territories) if (present.get(t.id)) members.get(keyOf(t))!.push(t);

  // ── 사건 지수 (영토!J) — 섬 안 최댓값은 그 기준일에 있는 영토에서 ──
  const J = new Map<string, number>();
  for (const [, ts] of members) {
    const max = Math.max(0, ...ts.map((t) => acc.get(t.id)!.I));
    for (const t of ts) J.set(t.id, logIndex(acc.get(t.id)!.I, max));
  }

  // ── 활동도 (영토!O~S) ──
  // 포럼은 명부 전체에서 최댓값을 잡는다. 분기가 바뀌어도 포럼 활동도는 오늘
  // 값 그대로다 (영토분기별!J 가 영토!S 를 그대로 가져온다). 다른 섬은 그
  // 기준일에 있는 영토끼리 다시 누른다. 행위자 원자료는 그때까지의 사건 수다
  const S = new Map<string, number>();
  const forumAll = territories.filter((t) => t.islandId === FORUM);
  const fmax = { raw: 0, posts: 0, threads: 0 };
  for (const t of forumAll) {
    for (const k of ['raw', 'posts', 'threads'] as const) {
      const v = rawNum(t[k]);
      if (v !== null && v > fmax[k]) fmax[k] = v;
    }
  }
  const rawOf = (t: Territory) =>
    t.islandId === ACTOR ? acc.get(t.id)!.rawCount : (rawNum(t.raw) ?? 0);
  for (const [, ts] of members) {
    const max = Math.max(0, ...ts.map(rawOf));
    for (const t of ts) {
      S.set(t.id, t.islandId === FORUM ? forumActivity(t, fmax) : logIndex(rawOf(t), max));
    }
  }

  // ── 영토 점수 (영토!T · U), 섬 점수, 섬 칸 목표 (섬!I · L) ──
  const U = new Map<string, number>();
  const isScore = new Map<string, number>();
  for (const [k, ts] of members) {
    let sum = 0;
    for (const t of ts) {
      const u = (J.get(t.id)! + w.base) * activityWeight(S.get(t.id)!, w);
      U.set(t.id, u);
      sum += u;
    }
    isScore.set(k, sum);
  }

  // 웹마다 따로 나눈다 (설계서 3.5 「오픈웹과 다크웹은 따로 계산」)
  const target = new Map<string, number>();
  for (const web of ['dark', 'open'] as const) {
    const keys = order.filter((k) => (members.get(k) ?? []).some((t) => t.web === web)
      || islands.some((i) => i.web === web && islandKey(i.id, i.web) === k));
    const got = islandTargets(keys, isScore, w.totalCells[web], w.islandAlpha);
    for (const [k, v] of got) target.set(k, v);
  }

  // ── 섬 안 칸 배분 (영토!V~AA) ──
  const cells = new Map<string, number>();
  for (const [k, ts] of members) {
    const { cells: got } = allocateCells(ts.map((t) => U.get(t.id)!), target.get(k) ?? 0);
    ts.forEach((t, i) => cells.set(t.id, got[i]));
  }

  const webScore: Record<Web, number> = { open: 0, dark: 0 };
  for (const [k, ts] of members) {
    if (ts.length) webScore[ts[0].web] += isScore.get(k) ?? 0;
  }

  const territoryMetrics: TerritoryMetrics[] = territories.map((t) => {
    const a = acc.get(t.id)!;
    const k = keyOf(t);
    const here = present.get(t.id)!;
    const u = here ? U.get(t.id)! : 0;
    const isl = isScore.get(k) ?? 0;
    const act = here ? S.get(t.id)! : 0;
    return {
      territoryId: t.id,
      islandKey: k,
      web: t.web,
      present: here,
      score: u,
      eventScoreSum: a.I,
      eventIndex: here ? J.get(t.id)! : 0,
      cells: here ? cells.get(t.id) ?? 0 : 0,
      shareInIsland: isl > 0 ? (u / isl) * 100 : 0,
      shareInWeb: webScore[t.web] > 0 ? (u / webScore[t.web]) * 100 : 0,
      activity: act,
      activityWeight: here ? activityWeight(act, w) : 0,
      surge7d: a.AF - a.AG,
      eventCount: a.H,
      recent30: a.AB,
      prev30: a.AC,
      countChangeRate30d: a.AC === 0 ? null : ((a.AB - a.AC) / a.AC) * 100,
      status: a.AB >= 1 ? '활성' : '관측 중',
      firstEventAt: a.firstAt,
      lastEventAt: a.lastAt,
    };
  });

  const islandMetrics: IslandMetrics[] = islands.map((i) => {
    const k = islandKey(i.id, i.web);
    const ms = territoryMetrics.filter((m) => m.islandKey === k && m.present);
    return {
      islandKey: k,
      islandId: i.id,
      web: i.web,
      score: isScore.get(k) ?? 0,
      target: target.get(k) ?? 0,
      cells: ms.reduce((acc2, m) => acc2 + m.cells, 0),
      // 섬!O = ROUND(AVERAGEIFS(활동도)) — 영토가 없으면 0
      avgActivity: ms.length ? excelRound(ms.reduce((s2, m) => s2 + m.activity, 0) / ms.length) : 0,
      eventCount: ms.reduce((s2, m) => s2 + m.eventCount, 0),
    };
  });

  const webCells: Record<Web, number> = { open: 0, dark: 0 };
  for (const m of territoryMetrics) webCells[m.web] += m.cells;
  const eventCount: Record<Web, number> = { open: 0, dark: 0 };
  const webOf = new Map(territories.map((t) => [t.id, t.web]));
  for (const e of events) {
    if (counted.has(e.id)) eventCount[webOf.get(e.territoryId) ?? 'dark'] += 1;
  }

  return { d, territories: territoryMetrics, islands: islandMetrics, webScore, webCells, eventCount };
}
