// Minimal Playwright setup, added specifically to cover the league
// multiselect consolidation bug (see tests-e2e/league-multiselect.spec.js)
// -- no build step needed, public/ is plain static HTML/JS/CSS served as-is.
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests-e2e",
  fullyParallel: true,
  webServer: {
    command: "python3 -m http.server 4173 --directory public",
    url: "http://127.0.0.1:4173/index.html",
    reuseExistingServer: !process.env.CI,
  },
  use: {
    baseURL: "http://127.0.0.1:4173",
  },
});
