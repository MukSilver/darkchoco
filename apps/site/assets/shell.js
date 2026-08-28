// 머리띠 · 데이터 읽기 · 검사. 세 구역이 같이 씁니다.

const NAV = [
  { href: "/guide/", label: "내 정보 확인" },
  { href: "/map/", label: "생태계 지도" },
  { href: "/wiki/", label: "조사 자료" },
];

export function mountHead(current) {
  // 배포 뿌리. 루트 배포면 빈 문자열입니다.
  // 하위 경로에 올릴 때만 <meta name="dc-base" content="/어디"> 한 줄을 답니다.
  const meta = document.querySelector('meta[name="dc-base"]');
  const base = meta ? meta.content.replace(/\/$/, "") : "";
  const head = document.createElement("header");
  head.className = "shell-head";
  head.innerHTML =
    `<a class="brand" href="${base}/">다크초코</a>` +
    `<nav class="shell-nav">` +
    NAV.map(n =>
      `<a href="${base}${n.href}"${n.href.includes(current) ? ' aria-current="page"' : ""}>${n.label}</a>`
    ).join("") +
    `</nav>`;
  document.body.prepend(head);
  return base;
}

// 예시 데이터면 화면 맨 위에 크게 답니다.
export function mountSampleWarning(meta) {
  if (!meta || !meta.is_sample) return;
  const el = document.createElement("div");
  el.className = "sample-warn";
  el.innerHTML =
    `<span>예시 데이터입니다</span>` +
    `<small>자리 이름은 실제이고 숫자는 UI 구조 설명용입니다. 그대로 인용하지 마십시오.</small>`;
  document.querySelector(".shell-head").after(el);
}

const DOMAINISH = /\b[A-Za-z0-9][A-Za-z0-9-]{1,30}\.(?:io|is|in|to|net|com|onion|st|cx|ws|cc|su|ru|as|pw)\b/;

// 데이터를 읽자마자 계약을 검사합니다. 어기면 그 요소만 빼고 콘솔에 적습니다.
// 도메인이 섞여 들어오면 아예 멈춥니다.
export function validate(data) {
  const problems = [];
  const ids = new Set((data.places || []).map(p => p.id));
  const caseOf = Object.fromEntries((data.places || []).map(p => [p.id, p.cases || 0]));
  const layerOf = Object.fromEntries((data.places || []).map(p => [p.id, p.layer]));

  for (const p of data.places || []) {
    if (DOMAINISH.test(p.name)) {
      throw new Error(`자리 이름에 도메인이 있습니다: ${p.id}. 데이터를 고치기 전에는 그리지 않습니다.`);
    }
  }

  data.flows = (data.flows || []).filter(f => {
    if (!ids.has(f.from) || !ids.has(f.to)) {
      problems.push(`없는 자리를 잇는 선: ${f.from} → ${f.to}`);
      return false;
    }
    if (f.cases != null && f.cases > Math.min(caseOf[f.from], caseOf[f.to])) {
      problems.push(`선의 건수가 자리보다 큽니다: ${f.from} → ${f.to} (${f.cases}건)`);
      return false;
    }
    if (f.kind === "drop" && layerOf[f.from] !== "sky") {
      problems.push(`내려가는 선인데 출발이 위층이 아닙니다: ${f.from} → ${f.to}`);
      return false;
    }
    if (f.kind === "rise" && layerOf[f.from] !== "deep") {
      problems.push(`올라오는 선인데 출발이 아래층이 아닙니다: ${f.from} → ${f.to}`);
      return false;
    }
    return true;
  });

  for (const c of data.cases || []) {
    const bad = (c.hops || []).map(h => h.place).filter(id => !ids.has(id));
    if (bad.length) problems.push(`사건 ${c.id}의 경로에 없는 자리: ${bad.join(", ")}`);
    // 허위로 판정한 사고에 확인된 항목이 있으면 안 됩니다
    if (c.gate === "blocked" && Object.values(c.items || {}).includes("confirmed")) {
      problems.push(`허위로 판정한 사건 ${c.id}에 확인된 항목이 있습니다`);
    }
    // 층이 자리와 어긋나면 안 됩니다
    for (const h of c.hops || []) {
      const pp = (data.places || []).find(x => x.id === h.place);
      if (pp && pp.layer !== h.layer) problems.push(`사건 ${c.id}의 ${h.place} 층이 어긋납니다`);
    }
  }

  const s = data.stats || {};
  const order = ["reported", "matched", "circulating", "judged"];
  for (let i = 1; i < order.length; i++) {
    if (s[order[i]] > s[order[i - 1]]) {
      problems.push(`깔때기 순서가 뒤집혔습니다: ${order[i - 1]}=${s[order[i - 1]]} < ${order[i]}=${s[order[i]]}`);
    }
  }

  if (problems.length) {
    console.warn("[데이터 계약 위반]\n" + problems.map(p => " · " + p).join("\n"));
  }
  return { data, problems };
}

export async function loadData(base) {
  const res = await fetch(`${base}/data/leak-map.json`, { cache: "no-store" });
  if (!res.ok) throw new Error(`데이터를 못 읽었습니다 (${res.status}). 서버로 띄웠는지 확인하십시오.`);
  return validate(await res.json());
}

// 구역 사이에 사건을 넘깁니다. 지도 → 가이드, 가이드 → 지도.
export function currentCase() {
  const v = new URLSearchParams(location.search).get("case");
  return v == null ? null : Number(v);
}

export function linkToCase(base, area, id) {
  return `${base}/${area}/?case=${id}`;
}

export function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else n.setAttribute(k, v);
  }
  for (const kid of kids) n.append(kid);
  return n;
}


// 확인된 항목만 골라냅니다. 주장은 조치의 입력이 아닙니다.
export function confirmedItems(c) {
  return Object.entries(c.items || {}).filter(([, v]) => v === "confirmed").map(([k]) => k);
}
export function claimedItems(c) {
  return Object.entries(c.items || {}).filter(([, v]) => v === "claimed").map(([k]) => k);
}

// 그 사고가 지금 어디까지 갔는가. 마지막으로 확인된 자리의 층과 대륙이 정합니다.
export const REACH = {
  "deep-only": { label: "아직 다크웹 안에서만 확인됐습니다",
                 sub: "계정이나 주소를 알아야 볼 수 있는 곳까지입니다" },
  "surfaced":  { label: "오픈웹까지 올라왔습니다",
                 sub: "가입만 하면 볼 수 있는 곳에 있습니다" },
  "public":    { label: "검색에 걸리는 곳까지 갔습니다",
                 sub: "회수를 요청해도 되돌리기 어렵습니다" },
  "unknown":   { label: "어디까지 갔는지 아직 못 봤습니다",
                 sub: "자리를 확인하지 못했습니다" },
};
