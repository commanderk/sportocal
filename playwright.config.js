// Minimal Playwright setup, added specifically to cover the league
// multiselect consolidation bug (see tests-e2e/league-multiselect.spec.js)
// -- no build step needed, public/ is plain static HTML/JS/CSS served as-is.
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests-e2e",
  fullyParallel: true,
  // CI (see .github/workflows/test.yml's e2e job): serial + one retry
  // against runner jitter, and an HTML report (with a trace of the retried
  // attempt) that the workflow uploads as an artifact on failure -- the
  // default CI reporter ("dot") doesn't write one.
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["dot"], ["html", { open: "never" }]] : "list",
  webServer: {
    command: "python3 -m http.server 4173 --directory public",
    url: "http://127.0.0.1:4173/index.html",
    reuseExistingServer: !process.env.CI,
  },
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "on-first-retry",
  },
});
