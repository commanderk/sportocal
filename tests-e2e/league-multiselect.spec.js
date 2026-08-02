// Regression coverage for a bug where re-checking an individual club that
// had been unchecked from a fully-selected league did not collapse the
// selection back into the single "<Liga> (Alle Vereine)" chip -- only a
// fresh click on the league's own master checkbox did. Root cause: the
// "fully selected" collapse was only performed inside the master
// checkbox's own change handler, never re-derived after an individual
// club's checkbox changed. Fixed by consolidateFullyCoveredLeagueGroups()
// in app.js, run on every selection change.
import { test, expect } from "@playwright/test";

const LEAGUE_LABEL = "1. Bundesliga Männer";
const GROUP_CHIP_TEXT = `${LEAGUE_LABEL} (Alle Vereine)`;

// Returns, in DOM order, the club rows belonging to the given league's
// section of the combo panel (the header + rows aren't wrapped in their own
// container, they're flat siblings inside #football-combo-body, so this
// walks siblings until the next league header). `index` is each row's
// position among ALL .club-row elements on the page, which stays stable
// for building an unambiguous Playwright locator via .nth().
async function leagueClubRows(page, leagueLabelSubstring) {
  return page.evaluate((label) => {
    const body = document.getElementById("football-combo-body");
    const children = [...body.children];
    const headIdx = children.findIndex(
      (el) => el.classList.contains("league-group-head") && el.textContent.includes(label)
    );
    if (headIdx === -1) throw new Error(`league head not found for "${label}"`);
    const allClubRows = [...document.querySelectorAll(".club-row")];
    const rows = [];
    for (let i = headIdx + 1; i < children.length; i++) {
      const el = children[i];
      if (el.classList.contains("league-group-head")) break;
      rows.push({
        index: allClubRows.indexOf(el),
        name: el.textContent.trim(),
      });
    }
    return rows;
  }, leagueLabelSubstring);
}

test.beforeEach(async ({ page }) => {
  await page.goto("/index.html");
  await page.locator("#football-combo-trigger").click();
  const head = page.locator(".league-group-head", { hasText: LEAGUE_LABEL });
  await expect(head).toBeVisible();
  // Select the whole league via its own master checkbox -- the pre-existing,
  // already-correct path that produces the single group chip.
  await head.locator('input[type="checkbox"]').click();
  await expect(page.locator("#football-chips .chip", { hasText: GROUP_CHIP_TEXT })).toBeVisible();
});

test("re-checking the same unchecked club collapses back to the league chip", async ({ page }) => {
  const rows = await leagueClubRows(page, LEAGUE_LABEL);
  expect(rows.length).toBeGreaterThanOrEqual(2);
  const target = rows[0];
  const checkbox = page.locator(".club-row").nth(target.index).locator('input[type="checkbox"]');

  await checkbox.uncheck();
  await expect(page.locator("#football-chips .chip", { hasText: GROUP_CHIP_TEXT })).toHaveCount(0);
  await expect(page.locator("#football-chips .chip", { hasText: target.name })).toHaveCount(0);

  await checkbox.check();
  await expect(page.locator("#football-chips .chip", { hasText: GROUP_CHIP_TEXT })).toBeVisible();
  await expect(page.locator("#football-chips .chip")).toHaveCount(1);
});

test("re-checking a DIFFERENT unchecked club also collapses back (not order/last-club dependent)", async ({
  page,
}) => {
  const rows = await leagueClubRows(page, LEAGUE_LABEL);
  expect(rows.length).toBeGreaterThanOrEqual(2);
  // Deliberately the second row, not the first (see test above), to prove
  // the fix is a generic Set-vs-full-roster comparison, not something that
  // happens to only work for whichever club was clicked first in testing.
  const target = rows[1];
  const checkbox = page.locator(".club-row").nth(target.index).locator('input[type="checkbox"]');

  await checkbox.uncheck();
  await expect(page.locator("#football-chips .chip", { hasText: GROUP_CHIP_TEXT })).toHaveCount(0);

  await checkbox.check();
  await expect(page.locator("#football-chips .chip", { hasText: GROUP_CHIP_TEXT })).toBeVisible();
  await expect(page.locator("#football-chips .chip")).toHaveCount(1);
});
