// Regression coverage for a bug where a league with only partial club
// coverage in clubs.json (scope !== "full", e.g. Regionalliga Südwest --
// only Stuttgarter Kickers of ~18 real clubs is tracked) could be
// misrepresented as "(Alle Vereine)" selected: the collapse logic compared
// the current selection against the *tracked* roster, not the league's real
// size, so selecting the one available club looked identical to selecting
// "the whole league". Fixed by having both the dropdown's master checkbox
// (renderFootballCombo()) and the auto-collapse logic
// (consolidateFullyCoveredLeagueGroups()) in app.js skip any league whose
// `scope` isn't "full".
import { test, expect } from "@playwright/test";

const INCOMPLETE_LEAGUE_LABEL = "Regionalliga Südwest";
const FULL_LEAGUE_LABEL = "1. Bundesliga Männer";

test.beforeEach(async ({ page }) => {
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
  expect(rows).toEqual(["Stuttgarter Kickers"]);
});

test("selecting the only tracked club of a scope !== \"full\" league stays an individual chip", async ({ page }) => {
  const row = page.locator(".club-row", { hasText: "Stuttgarter Kickers" });
  await row.locator('input[type="checkbox"]').check();

  await expect(page.locator("#football-chips .chip", { hasText: "Stuttgarter Kickers" })).toBeVisible();
  await expect(page.locator("#football-chips .chip", { hasText: "Alle Vereine" })).toHaveCount(0);
  await expect(page.locator("#football-chips .chip", { hasText: INCOMPLETE_LEAGUE_LABEL })).toHaveCount(0);
});

test("regression: a scope: \"full\" league still shows its \"Alle Vereine\" master checkbox", async ({ page }) => {
  const head = page.locator(".league-group-head", { hasText: FULL_LEAGUE_LABEL });
  await expect(head).toBeVisible();
  await expect(head.locator('input[type="checkbox"]')).toHaveCount(1);
  await expect(head).toContainText("Alle Vereine");
});
