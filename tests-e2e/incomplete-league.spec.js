// Regression coverage for a bug where a league with only partial club
// coverage in clubs.json (scope !== "full") could be misrepresented as
// "(Alle Vereine)" selected: the collapse logic compared the current
// selection against the *tracked* roster, not the league's real size, so
// selecting the one available club looked identical to selecting "the whole
// league". Fixed by having both the dropdown's master checkbox
// (renderFootballCombo()) and the auto-collapse logic
// (consolidateFullyCoveredLeagueGroups()) in app.js skip any league whose
// `scope` isn't "full".
//
// History: the bug surfaced with Regionalliga Südwest, where only Stuttgarter
// Kickers was tracked. Since #12 that league is fully covered (all 18 clubs,
// scope: "full"), and no real league is partial anymore -- so these tests
// inject a synthetic partial league ("Testliga Teilabdeckung", one tracked
// club "Test-Verein") into the real leagues.json/clubs.json responses via
// page.route(), keeping the scope !== "full" code paths covered independent
// of the live data. No fixture files are added under public/.
import { test, expect } from "@playwright/test";

const FIXTURE_LEAGUE = {
  id: "test-teilabdeckung",
  competition: "Testliga Teilabdeckung",
  gender: "men",
  scope: "club-filter",
};
const FIXTURE_CLUB = {
  id: "test-verein",
  name: "Test-Verein",
  shortName: "Test-Verein",
  colorHex: "#777777",
  teams: { men: { league: FIXTURE_LEAGUE.competition } },
};
const INCOMPLETE_LEAGUE_LABEL = "Testliga Teilabdeckung Männer";
const FULL_LEAGUE_LABEL = "1. Bundesliga Männer";

// Serves the real file with `extra` appended -- app.js loads both via
// fetch("data/<name>.json", { cache: "no-store" }).
async function appendToJsonResponse(page, name, extra) {
  await page.route(`**/data/${name}.json`, async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    await route.fulfill({ response, json: [...json, extra] });
  });
}

test.beforeEach(async ({ page }) => {
  await appendToJsonResponse(page, "leagues", FIXTURE_LEAGUE);
  await appendToJsonResponse(page, "clubs", FIXTURE_CLUB);
  await page.goto("/index.html");
  await page.locator("#football-combo-trigger").click();
});

test("a scope !== \"full\" league shows no \"Alle Vereine\" master checkbox, only its tracked club(s)", async ({
  page,
}) => {
  const head = page.locator(".league-group-head", { hasText: INCOMPLETE_LEAGUE_LABEL });
  await expect(head).toBeVisible();
  await expect(head.locator('input[type="checkbox"]')).toHaveCount(0);
  await expect(head).not.toContainText("Alle Vereine");

  // Exactly one club row directly follows this header, before the next one.
  const rows = await page.evaluate((label) => {
    const body = document.getElementById("football-combo-body");
    const children = [...body.children];
    const headIdx = children.findIndex(
      (el) => el.classList.contains("league-group-head") && el.textContent.includes(label)
    );
    const out = [];
    for (let i = headIdx + 1; i < children.length; i++) {
      const el = children[i];
      if (el.classList.contains("league-group-head")) break;
      out.push(el.textContent.trim());
    }
    return out;
  }, INCOMPLETE_LEAGUE_LABEL);
  expect(rows).toEqual([FIXTURE_CLUB.name]);
});

test("selecting the only tracked club of a scope !== \"full\" league stays an individual chip", async ({ page }) => {
  const row = page.locator(".club-row", { hasText: FIXTURE_CLUB.name });
  await row.locator('input[type="checkbox"]').check();

  await expect(page.locator("#football-chips .chip", { hasText: FIXTURE_CLUB.name })).toBeVisible();
  await expect(page.locator("#football-chips .chip", { hasText: "Alle Vereine" })).toHaveCount(0);
  await expect(page.locator("#football-chips .chip", { hasText: INCOMPLETE_LEAGUE_LABEL })).toHaveCount(0);
});

test("regression: a scope: \"full\" league still shows its \"Alle Vereine\" master checkbox", async ({ page }) => {
  const head = page.locator(".league-group-head", { hasText: FULL_LEAGUE_LABEL });
  await expect(head).toBeVisible();
  await expect(head.locator('input[type="checkbox"]')).toHaveCount(1);
  await expect(head).toContainText("Alle Vereine");
});
