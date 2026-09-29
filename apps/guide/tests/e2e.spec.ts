// 빌드 결과를 실제 브라우저로 확인합니다. 사고 자료는 스냅샷에서 읽어 오므로 자료가 바뀌어도 시험이 깨지지 않습니다.
// 사고 목록은 저장소에 없습니다. 새 클론처럼 목록이 비어 있으면 사고가 있어야 하는 시험은 건너뜁니다.
import { test, expect, type Page } from "@playwright/test";
import cases from "../src/data/cases.json" with { type: "json" };

type Case = (typeof cases)[number];
const real = cases.filter((c) => c.gate !== "fake");
const fake = cases.find((c) => c.gate === "fake");
const errsOf = (page: Page) => (page as unknown as { errs: string[] }).errs;

test.beforeEach(async ({ page }) => {
  const errs: string[] = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
  (page as unknown as { errs: string[] }).errs = errs;
});

/** 섬이 살아난 뒤에 단추를 누르도록 기다립니다 (Astro 는 살아나면 astro-island 의 ssr 표시를 뗍니다) */
const ready = (page: Page) => page.waitForSelector("astro-island:not([ssr])", { state: "attached" });

/** 사고 페이지를 열고, 확인 항목이 없으면 주장 항목을 눌러 조치가 뜨게 합니다 */
async function openCase(page: Page, c: Case) {
  await page.goto(`/cases/${c.id}/`); await ready(page);
  if (!c.confirmed.length) for (const id of c.claimed.slice(0, 4)) await page.locator(`.tile[data-src="item:${id}"]`).click();
  await expect(page.locator("#sec-next .nt")).toBeVisible();
}

test("사고 페이지: 조치가 뜨고, 완료와 되돌리기가 되고, 새로고침해도 남는다", async ({ page }) => {
  test.skip(!real.length, "허위가 아닌 사고가 없음");
  const c = real[0];
  await openCase(page, c);
  const first = await page.locator("#sec-next .nt").innerText();
  const before = await page.locator(".progress h3").innerText();
  await expect(page.locator("#sec-next .fx .e")).toHaveCount(1);
  // 완료 뒤 바로 되돌리기 (알림은 5초만 떠 있음)
  await page.locator("#sec-next button.btn").click();
  await expect(page.locator("#toast")).toHaveClass(/on/);
  await page.locator("#toast button[data-undo]").click();
  await expect(page.locator(".progress h3")).toHaveText(before);
  await expect(page.locator("#sec-next .nt")).toHaveText(first);
  // 다시 완료하면 다음 할 일이 바뀌고 새로고침해도 남는다
  await page.locator("#sec-next button.btn").click();
  await expect(page.locator("#sec-next .nt")).not.toHaveText(first);
  const after = await page.locator(".progress h3").innerText();
  expect(after).not.toBe(before);
  await page.reload();
  await expect(page.locator(".progress h3")).toHaveText(after);
  expect(errsOf(page)).toEqual([]);
});

test("안내문 경로: 항목을 고르고 대응 한 장으로 넘어간다", async ({ page }) => {
  await page.goto("/notice/1/");
  await page.getByRole("link", { name: "정상적인 안내 같아요" }).click();
  await expect(page).toHaveURL(/\/notice\/2\/$/); await ready(page);
  await page.getByRole("button", { name: "유출됐다고 적혀 있어요" }).click();
  await page.getByRole("link", { name: "다음" }).click(); await ready(page);
  for (const id of ["name", "phone", "rrn"]) await page.locator(`.tile[data-src="item:${id}"]`).click();
  await page.getByRole("button", { name: "3개월 이내" }).click();
  await page.getByRole("link", { name: "대응 방법 보기" }).click();
  await expect(page).toHaveURL(/\/plan\/$/);
  await expect(page.locator("h1 em")).toHaveText(/명의 도용|사칭 전화와 문자/);
  await expect(page.locator(".trail.est")).toHaveCount(1);
  await expect(page.locator(".progress h3")).toHaveText(/대응 \d+개 중 2개 완료/);
  expect(errsOf(page)).toEqual([]);
});

test("허위 사고는 조치를 내지 않는다", async ({ page }) => {
  test.skip(!fake, "허위 사고가 없음");
  await page.goto(`/cases/${fake!.id}/`);
  await expect(page.locator(".alarm h1")).toHaveText("허위로 판정된 사고예요");
  await expect(page.locator("#sec-rest")).toHaveCount(0);
});

test("샘플 미확인 사고는 주장 항목을 점선으로 보이고 조치를 내지 않는다", async ({ page }) => {
  const w = cases.find((c) => c.gate === "wait" && c.claimed.length);
  test.skip(!w, "샘플 미확인 사고가 없음");
  await page.goto(`/cases/${w!.id}/`);
  await expect(page.locator(".tile.cl")).toHaveCount(w!.claimed.length);
  await expect(page.locator("h1")).toHaveText(/유출된 항목을 선택하세요/);
  await expect(page.locator("#sec-rest")).toHaveCount(0);
});

test("입구: 이어서 보기 카드가 진행을 읽는다", async ({ page }) => {
  test.skip(!real.length, "허위가 아닌 사고가 없음");
  await openCase(page, real[0]);
  await page.locator("#sec-next button.btn").click();
  await page.goto("/");
  await expect(page.locator(".resume b")).toHaveText("지난번에 보던 대응 안내가 있어요");
  await expect(page.locator(".resume .small")).toContainText("3개 완료");
  await page.getByRole("button", { name: "기록 지우기" }).click();
  await expect(page.locator(".resume")).toHaveCount(0);
});

test("사고 목록: 업종으로 거르기", async ({ page }) => {
  test.skip(!cases.length, "사고가 없음");
  await page.goto("/cases/");
  await expect(page.locator(".case")).toHaveCount(cases.length);
  const ind = cases[0].industry, n = cases.filter((c) => c.industry === ind).length;
  await page.locator(".inds .ind", { hasText: ind }).click();
  await expect(page.locator(".case")).toHaveCount(n);
});

test("쉬운 보기: 전화와 방문 방법이 먼저 나온다", async ({ page }) => {
  test.skip(!real.length, "허위가 아닌 사고가 없음");
  await openCase(page, real[0]);
  await page.getByRole("button", { name: "온라인 신청이 어려워요" }).click();
  await expect(page.locator("#sec-next .how h3, #sec-next .small").first()).toBeVisible();
  const links = page.locator("#sec-next a[href^='http']");
  await expect(links).toHaveCount(0);
});

test("보안: 외부 요청이 없다", async ({ page }) => {
  const hosts = new Set<string>();
  page.on("request", (r) => hosts.add(new URL(r.url()).host));
  await page.goto(real.length ? `/cases/${real[0].id}/` : "/");
  await page.waitForLoadState("networkidle");
  expect([...hosts].filter((h) => !h.startsWith("localhost") && !h.startsWith("127.0.0.1"))).toEqual([]);
});

/* 프로토타입 5판과 같은 동작인지 (2026-09-22 전수 비교 뒤 추가) */

test("겉모습: 문과 사고 줄은 링크여도 밑줄과 파란 글자가 없다", async ({ page }) => {
  await page.goto("/");
  const door = page.locator("a.door").first();
  expect(await door.evaluate((el) => getComputedStyle(el).textDecorationLine)).toBe("none");
  expect(await door.evaluate((el) => getComputedStyle(el).color)).toBe(await page.locator("h1").evaluate((el) => getComputedStyle(el).color));
  await page.goto("/cases/");
  if (cases.length) {
    const row = page.locator("a.case").first();
    expect(await row.evaluate((el) => getComputedStyle(el).textDecorationLine)).toBe("none");
  }
  expect(await page.locator("a.back").evaluate((el) => getComputedStyle(el).textDecorationLine)).toBe("none");
});

test("사고 목록: 항목 아이콘이 겹치지 않는다", async ({ page }) => {
  await page.goto("/cases/");
  for (const c of cases) {
    const n = await page.locator(`a.case[href="/cases/${c.id}/"] .icons svg`).count();
    expect(n).toBe(new Set([...c.confirmed, ...c.claimed]).size);
  }
});

test("사고 목록: 업종을 고르면 주소가 바뀌고 뒤로 가기로 돌아온다", async ({ page }) => {
  test.skip(!cases.length, "사고가 없음");
  await page.goto("/cases/"); await ready(page);
  const ind = cases[0].industry;
  await page.locator(".inds .ind", { hasText: ind }).click();
  await expect(page).toHaveURL(new RegExp("ind=" + encodeURIComponent(ind)));
  await page.goBack();
  await expect(page).toHaveURL(/\/cases\/$/);
  await expect(page.locator(".case")).toHaveCount(cases.length);
});

test("안내문 경로: 밖에서 들어오면 새로 시작하고, 안에서는 고른 값이 이어진다", async ({ page }) => {
  await page.goto("/notice/3/"); await ready(page);
  await page.locator('.tile[data-src="item:name"]').click();
  await page.locator('.tile[data-src="item:rrn"]').click();
  await page.getByRole("button", { name: "3개월 이내" }).click();
  await page.getByRole("link", { name: "대응 방법 보기" }).click();
  await expect(page).toHaveURL(/\/plan\/$/);
  await page.locator("#sec-next button.btn").click();
  const after = await page.locator(".progress h3").innerText();
  // 항목 다시 선택으로 돌아가면 고른 값이 그대로
  await page.getByRole("link", { name: "항목 다시 선택" }).click(); await ready(page);
  await expect(page.locator('.tile[data-src="item:rrn"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "3개월 이내" })).toHaveAttribute("aria-pressed", "true");
  // 항목을 바꿔 다시 오면 새 항목이 반영되고 완료 표시는 남는다
  await page.locator('.tile[data-src="item:phone"]').click();
  await page.getByRole("link", { name: "대응 방법 보기" }).click();
  await expect(page.locator('.tile[data-src="item:phone"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".progress h3")).toHaveText(after.replace(/대응 \d+개/, "대응 " + (await page.locator(".tl2 i").count()) + "개"));
  // 뒤로 가기는 안내문 안이라 이어짐
  await page.goBack();
  await expect(page.locator('.tile[data-src="item:phone"]')).toHaveAttribute("aria-pressed", "true");
  // 입구에서 다시 들어오면 비어 있음
  await page.goto("/");
  await page.getByRole("link", { name: "안내문으로 시작하기" }).click();
  await page.getByRole("link", { name: "정상적인 안내 같아요" }).click();
  await page.getByRole("link", { name: "다음" }).click();
  await expect(page.locator(".tile[aria-pressed='true']")).toHaveCount(0);
});

test("안내문 1단계: 의심스러워요는 단계를 오가도 남는다", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "안내문으로 시작하기" }).click(); await ready(page);
  await page.getByRole("button", { name: "의심스러워요" }).click();
  await expect(page.locator(".alarm")).toBeVisible();
  await page.getByRole("link", { name: "그래도 대응 방법 보기" }).click();
  await page.getByRole("link", { name: "이전" }).click(); await ready(page);
  await expect(page.locator(".alarm")).toBeVisible();
});

test("대응 한 장: 다음 할 일이 바뀌면 카드가 새로 나타나고, 막대는 차오르고, 초점이 남는다", async ({ page }) => {
  test.skip(!real.length, "허위가 아닌 사고가 없음");
  await openCase(page, real[0]);
  const c = real[0];
  if (c.stageIdx !== null && c.stageIdx > 0) await expect(page.locator(".trail .tf")).toHaveCSS("width", /[1-9]/);
  await page.locator("#sec-next button.btn").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#sec-next")).toHaveClass(/enter/);
  await expect(page.locator("#sec-next button.btn")).toBeFocused();
  const later = page.locator("#sec-next .txtbtn");
  if (await later.count()) { await later.click(); await expect(page.locator("#sec-next button.btn")).toBeFocused(); }
});

test("연결 강조는 대응 한 장에서만 된다", async ({ page }) => {
  await page.goto("/notice/3/"); await ready(page);
  await page.locator('.tile[data-src="item:name"]').hover();
  await expect(page.locator("#app .dim")).toHaveCount(0);
  test.skip(!real.length, "허위가 아닌 사고가 없음");
  await openCase(page, real[0]);
  await page.locator(".rk").first().hover();
  expect(await page.locator("#app .dim").count()).toBeGreaterThan(0);
});

test("보기 설정: Esc 로 닫히고 단추로 초점이 돌아온다", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 }); // 좁은 화면에서만 단추로 여닫음
  await page.goto("/"); await ready(page);
  await page.locator("#prefsBtn").click();
  await expect(page.locator("#prefs")).toHaveClass(/open/);
  await page.keyboard.press("Escape");
  await expect(page.locator("#prefs")).not.toHaveClass(/open/);
  await expect(page.locator("#prefsBtn")).toBeFocused();
});
