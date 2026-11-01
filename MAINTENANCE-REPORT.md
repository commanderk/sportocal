# Wartungs-Report: Dependency-Updates & Security-Check

Branch: `chore/maintenance-2026-11` (von `main` @ `fe688ba`, 2026-11-01). Nicht gepusht.

Commits:

| Commit | Inhalt |
|---|---|
| `589d218` | Python: `uv.lock` aktualisiert |
| `3c06da7` | Node: `@playwright/test` 1.62.1 → 1.64.1 |
| `490dec8` | Actions: checkout v7.0.1, setup-python v7.1.0, SHA-gepinnt |
| `880afe9` | Security: CR/CRLF in ICS-Textfeldern neutralisieren (+2 Tests) |
| `d1c8f25` | Security: `test.yml` mit `permissions: contents: read`, `persist-credentials: false` |
| (dieser) | `MAINTENANCE-REPORT.md` |

## 1. Updates

| Paket / Action | alt → neu | Release | Breaking Changes | umgesetzt |
|---|---|---|---|---|
| `tzdata` (Runtime) | 2026.3 → 2026.6 | – | nein | ja (`uv.lock`) |
| `pytest` + Deps (dev) | fehlte im Lock → 9.2.0 | – | nein | ja (`uv.lock`, s. u.) |
| `@playwright/test` | 1.62.1 → 1.64.1 | 2026-10-14 | ja, betrifft uns nicht¹ | ja |
| Chromium (Playwright) | → 156.0.8078.4 | – | – | lokal installiert |
| `actions/checkout` | v5 → v7.0.1 | 2026-07-20 | ja, betrifft uns nicht² | ja |
| `actions/setup-python` | v6 → v7.1.0 | 2026-10-22 | ja, betrifft uns nicht³ | ja |
| Python im Workflow | 3.12 | – | – | unverändert (s. Offene Punkte) |

¹ 1.64: `screen` wird aus den Device-Descriptors übernommen. `playwright.config.js` nutzt keine `devices`, daher ohne Auswirkung. 1.63 hat keine Breaking Changes.
² v6: Credentials liegen in einer separaten Datei unter `$RUNNER_TEMP` statt in `.git/config`. Das authentifizierte `git push` in `update.yml` funktioniert weiterhin, da hier kein Docker-Container-Action im Spiel ist. Benötigt Runner ≥ 2.327.1, GitHub-hosted erfüllt das. v7: Fork-PR-Checkout bei `pull_request_target`/`workflow_run` wird blockiert; diese Trigger nutzen wir nicht.
³ v7: Input `pip-install` entfernt (nicht genutzt), EOL-Python-Versionen entfernt (3.12 nicht betroffen), ESM-Migration intern.

**`uv.lock`-Konsistenz:** Der Lockfile auf `main` enthielt das `[project.optional-dependencies].dev`-Extra (pytest) nicht, `uv lock --check` wäre also fehlgeschlagen. Er ist jetzt konsistent. Vercel installiert keine optionalen Extras, die Runtime-Abhängigkeit ist weiterhin nur `tzdata`. `requirements*.txt` und `pyproject.toml` sind inhaltlich unverändert.

**Workflows / Browser:** E2E-Tests laufen nicht in CI (`test.yml` führt nur `pytest` aus), daher muss kein Workflow für Browser-Installationen angepasst werden.

## 2. Security-Findings

### Hoch
Keine.

### Mittel

| Fundstelle | Befund | Status |
|---|---|---|
| `scripts/common.py:286` (`escape_text`) | Es wurde nur `\n` maskiert, nicht `\r`. Ein CR aus gescrapten Daten (`round`, `location`, `route.finish`, Teamnamen von OpenLigaDB/DFB/Wikipedia) wäre roh in `SUMMARY`/`DESCRIPTION`/`LOCATION`/VALARM-`DESCRIPTION` gelandet. Das hätte die Content-Line beendet und Property-Injection ermöglicht. | **umgesetzt**: CRLF/CR → `\n` vor dem Escaping, 2 neue Tests. Aktuelle Daten enthalten kein CR. Die erzeugte ICS-Ausgabe (alle Ligen + Renngruppen, 1.820 Events) ist **byte-identisch** zu `main` (abgesehen vom `DTSTAMP`). |
| `.github/workflows/test.yml` | Kein `permissions`-Block, der Job lief mit den Default-Token-Rechten des Repos (je nach Repo-Einstellung `write-all`). | **umgesetzt**: `permissions: contents: read`, Checkout mit `persist-credentials: false`. |

### Niedrig

| Fundstelle | Befund | Status |
|---|---|---|
| `.github/workflows/*.yml` | Actions waren per Tag referenziert (veränderbar). | **umgesetzt** für `actions/*`: Pinning auf Commit-SHA mit Versionskommentar. Weitere Actions gibt es nicht. Empfehlung: Dependabot für `github-actions` aktivieren, damit SHA-Pins aktuell bleiben. |
| `vercel.json` | Keine Security-Header gesetzt. | **Empfehlung** (nicht umgesetzt, s. Offene Punkte). |
| `.gitignore` | `.claude/` (enthält `settings.local.json`) wird nur über das globale Git-Ignore des Users (`~/.config/git/ignore`) ignoriert, nicht über das Repo. Auf einer anderen Maschine könnte die Datei versehentlich committet werden. `.env*` und `.vercel` sind korrekt ignoriert. | **Empfehlung**: `.claude/settings.local.json` in die Repo-`.gitignore` aufnehmen. Nicht umgesetzt, weil offen ist, ob andere `.claude/`-Inhalte (Skills, Settings) bewusst versioniert werden sollen. |
| `api/calendar_ics.py:229` (`filter_events`) | Aufwand O(Events × Tokens), keine Obergrenze für die Tokenanzahl. 5.000 Junk-Tokens ≈ 0,54 s lokal. Praktisch begrenzt durch das URL-Limit von Vercel (~14 KB ≈ 1.000 Tokens ≈ 0,1 s). | **Empfehlung** (optional): Tokens auf z. B. 500 kappen. Das ist eine Verhaltensänderung, daher nicht umgesetzt. |

### Info (geprüft, kein Handlungsbedarf)

- **API-Token `?t=`** (`api/calendar_ics.py`): Tokens werden ausschließlich als Set- und Dict-Lookup-Keys gegen `config.json`/`clubs.json` verwendet, nie in Pfaden. Snapshots werden per festem Glob `data/*.json` geladen. Getestet wurden Traversal (`../../etc/passwd:men`, `league:../../x:men`), CRLF, NUL, Unicode/Emoji, `__proto__`, leere Teile, nur Kommas, unbekannte IDs, 2.000 Duplikate und 10 MB Token: immer `200` ohne Exception, unbekannte Teile werden verworfen, leer/Whitespace ergibt `400`. `X-WR-CALNAME` wird nur aus Config-Daten (`shortName`, Liga-/Tier-Labels) gebaut, nie aus Token-Text. `Content-Disposition` ist statisch.
- **`X-WR-CALNAME` und `UID`** laufen nicht durch `escape_text()`. Die Quellen sind unkritisch: Config-Daten, numerische Match-IDs (Regex `\d+`), einzeilige Stage-Labels (`splitlines()[0]`). Bewusst unverändert, weil UIDs und Kalendertitel stabil bleiben müssen.
- **Workflows:** keine `${{ github.event.* }}`- oder Input-Interpolation in `run:`, kein `pull_request_target`, `workflow_dispatch` ohne Inputs. `update.yml` hat `contents: write` auf Workflow-Ebene; das ist minimal, weil es nur einen Job gibt und dieser pusht. `actionlint` 1.7.12: 0 Fehler.
- **Secrets:** Komplette Git-History (98 Commits, alle Branches) per Pattern-Scan geprüft (GitHub-/Slack-/AWS-/OpenAI-Tokens, Private Keys, `api_key=`, `password=`, Bearer, Vercel-Tokens): 0 Treffer. `.env`, `.vercel`, `.claude` waren nie getrackt. `gitleaks` ist lokal nicht installiert. Lokal liegt `.env.local` mit `VERCEL_OIDC_TOKEN`, ignoriert und nie committet.
- **Frontend `public/`:** Es gibt keine externen Scripts (nur `app.js`, `style.css`, `favicon.svg`). Das einzige `innerHTML` mit dynamischem Inhalt (`app.js:382`) bekommt nur `Intl.DateTimeFormat`-Ausgabe, alle Daten aus JSON/localStorage gehen über `textContent`/`style.*`. Die Subscribe-URL wird über `URL.searchParams.set()` gebaut. Kein XSS-Pfad gefunden.
- **Scraper `scripts/`:** Alle HTTP-Requests laufen über `http_get_text`/`http_get_json` (`common.py:402/417`) mit `timeout=20` und Retries, es gibt keine weiteren `urlopen`-Aufrufe. Snapshot-Dateinamen stammen aus `config.json` (`source_id`), nicht aus externem Inhalt. Es wird kein HTML generiert, nur JSON.
- **Vulnerabilities:** `npm audit`: 0. `pip-audit` (alle Pakete aus `uv.lock` inkl. dev): keine bekannten Schwachstellen.

## 3. Testergebnisse

| | Baseline (`main`) | nachher (Branch) |
|---|---|---|
| `pytest` | **141 passed** | **143 passed** (141 + 2 neue CRLF-Tests) |
| `npx playwright test` | 4 passed, **1 failed** | 4 passed, **1 failed** (derselbe Test) |
| `npm audit` | – | 0 vulnerabilities |
| `pip-audit` | – | No known vulnerabilities |
| `uv lock --check` | inkonsistent (dev-Extra fehlte) | OK |
| `actionlint` | – | 0 Fehler |

**E2E-Fehler schon in der Baseline:** `tests-e2e/incomplete-league.spec.js:21` erwartet für „Regionalliga Südwest“ *keine* „Alle Vereine“-Checkbox und genau einen Verein (Stuttgarter Kickers). Seit #12 (`bdcd03e`, volle Liga mit 18 Vereinen) ist `rlsw-kickers` aber `scope: "full"`, und in `public/data/leagues.json` gibt es überhaupt keine Liga mit `scope != "full"` mehr. Der Test ist also veraltet, das ist kein Regressionsfehler. Der Test bei `:47` („only tracked club … stays an individual chip“) ist grün, prüft unter den neuen Daten aber nicht mehr das, wofür er geschrieben wurde. Nicht angefasst, da außerhalb des Wartungs-Scopes.

**Flakiness:** Ein paralleler Lauf (3 Worker) endete einmal mit 4 Fehlern, alle mit 5-s-Timeouts. Drei Wiederholungen und ein Lauf mit `--workers=1` zeigten wieder exakt das Baseline-Ergebnis. Vermutlich ein lokales Last- bzw. Startup-Timing-Problem und kein Effekt des Updates.

Unverändert gegenüber `main` (verifiziert per `git diff`): `data/`, `public/data/`, `public/kalender.ics`, `robots.txt`, ICS-Titel/UIDs (byte-identische Ausgabe), Token-Format.

## 4. Offene Punkte (Entscheidung nötig)

1. **Veralteter E2E-Test `incomplete-league.spec.js`:** löschen, auf eine künstliche Fixture-Liga mit `scope: "club-filter"` umbauen oder die Code-Pfade für `scope != "full"` (app.js `consolidateFullyCoveredLeagueGroups()`, `build_calendar_name()`-Branch) ganz entfernen, falls keine solche Liga mehr geplant ist.
2. **Security-Header in `vercel.json`:** Vorschlag zum Testen in einer Preview:
   ```json
   "headers": [{
     "source": "/(.*)",
     "headers": [
       { "key": "X-Content-Type-Options", "value": "nosniff" },
       { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
       { "key": "Permissions-Policy", "value": "camera=(), microphone=(), geolocation=(), interest-cohort=()" },
       { "key": "X-Frame-Options", "value": "DENY" },
       { "key": "Content-Security-Policy", "value": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" }
     ]
   }]
   ```
   Risiko bei der CSP: Inline-`style`-Attribute in HTML oder inline `<script>` würden blockiert. `element.style.*` aus JS ist von `style-src` nicht betroffen, inline gesetzte `style="..."`-Attribute in HTML schon. Davon gibt es aktuell 3 in `index.html` und je 1 in `datenschutz.html`/`impressum.html`. Die müssten vorher in `style.css` wandern, oder die CSP bekommt `style-src 'self' 'unsafe-inline'`. Inline-`<script>` gibt es keine. Die CSP lässt sich zunächst als `Content-Security-Policy-Report-Only` ausrollen.
3. **`.claude/settings.local.json` in die Repo-`.gitignore`?** (s. Niedrig)
4. **Python-Version:** Für 3.12 gibt es nur noch Security-Releases (Bugfix-Support beendet, EOL Oktober 2028), also kein akuter Handlungsbedarf. Prüfen solltest du, welche Python-Version Vercel für `api/calendar_ics.py` tatsächlich nutzt: Es gibt keine `.python-version` und nur `requires-python = ">=3.12"`, Vercel könnte also eine neuere Version (3.13/3.14) wählen als CI (3.12). Eine `.python-version` mit `3.12` würde das angleichen.
5. **Token-Limit in der API** (optional, s. Niedrig).
6. **Dependabot** für `github-actions` (und ggf. `npm`/`uv`) aktivieren, damit SHA-Pins und Lockfiles nicht wieder wochenlang veralten.
7. **E2E in CI?** Aktuell laufen die Playwright-Tests nur lokal. Ein CI-Job würde veraltete Tests wie in Punkt 1 früher sichtbar machen.

## 5. Folgerunde

Bezieht sich auf die Punkte aus Abschnitt 4. Ein Commit pro Punkt, Punkt 2 hat zwei Stufen und damit zwei Commits. Weiterhin nicht gepusht.

| Punkt | umgesetzt | Commit |
|---|---|---|
| 1 – E2E-Test auf Fixture-Liga | ja | `caf1d49` |
| 2a – Inline-Styles → `style.css` | ja | `cb54035` |
| 2b – Security-Header / CSP Report-Only | ja | `d448726` |
| 3 – `.gitignore` | ja | `46c5ff6` |
| 4 – `.python-version` | ja | `569d6f2` |
| 5 – Token-Limit | entfällt | – |
| 6 – Dependabot | ja | `ccde7d4` |
| 7 – E2E in CI | ja | `9f63d87` |

### Punkt 1 – Fixture-Liga
- **E2E:** `tests-e2e/incomplete-league.spec.js` fängt `**/data/leagues.json` und `**/data/clubs.json` per `page.route()` ab (Pfade verifiziert: `fetchJson("data/…json")` in `app.js`, `fetch(path, { cache: "no-store" })`). Die Spec lädt die echten Antworten und hängt die Liga „Testliga Teilabdeckung“ (`id: test-teilabdeckung`, `scope: "club-filter"`) mit genau einem Verein „Test-Verein“ an. Unter `public/` liegen keine Fixture-Dateien. Alle drei Testfälle sind erhalten, (c) prüft weiterhin die echte „1. Bundesliga Männer“. Der Header-Kommentar nennt Regionalliga Südwest als Historie.
- **Backend:** `build_calendar_name()` war mit Inline-Daten getestet, aber unter der echten ID `rlsw-kickers`/„Regionalliga Südwest“. Für `filter_events()`/`build_response_body()` mit einer `club-filter`-Liga gab es keinen Test. Neu: Fixtures `club_filter_league`/`club_filter_club` in `tests/conftest.py`, der bestehende Test ist darauf umgestellt, dazu ein End-to-End-Test über `build_response_body()` (Spiel des getrackten Vereins gegen einen ungetrackten Gegner ist drin, fremde Spiele nicht; Kalendername „Sportocal – Test-Verein“ statt „Testliga Teilabdeckung (Männer)“).
- **Gegenprobe (Mutation):** Mit deaktivierten `scope`-Prüfungen in `app.js` schlagen E2E (a) und (b) fehl. Ohne den `scope`-Zweig in `build_calendar_name()` schlagen beide Backend-Tests fehl. Die Tests decken die Pfade also tatsächlich ab.

### Punkt 2 – Inline-Styles & Header
- **Stufe 1:** `a.wordmark { text-decoration: none; color: inherit; }` sowie `.preview-event-bar--red/--yellow/--blue`. Full-Page-Screenshots von index/impressum/datenschutz sind vorher/nachher **byte-identisch**. Die Preview-Balken sind initial nicht sichtbar, deshalb habe ich zusätzlich die berechneten Farben geprüft (rgb(217,43,28) / (232,180,0) / (15,95,217) = Originalwerte). `grep`: kein `style=`, kein Inline-`<script>`, keine `on*=`-Handler in `public/*.html`.
- **Stufe 2:** Header wie vorgegeben, `Permissions-Policy` ohne `interest-cohort`, CSP nur als **`Content-Security-Policy-Report-Only`**.
- **Lokal simuliert, nicht mit `vercel dev`** (Vercel CLI nicht installiert): Ein Python-Server hat `public/` ausgeliefert, den `headers`-Block aus `vercel.json` angewendet und `/api/calendar.ics` an die echte WSGI-App geleitet.
  - `/api/calendar.ics`: `Content-Type: text/calendar; charset=utf-8`, `Content-Disposition` und `Cache-Control` unverändert, die neuen Header kommen nur hinzu.
  - Der `headers`-Block setzt selbst keinen `Content-Type`. Den Typ von `/kalender.ics` bestimmt weiterhin Vercels Static-Serving (lokal kam er nur vom Python-Mimetype, das ist **nicht** aussagekräftig für Vercel).
  - CSP im Chromium: index (inkl. Combo öffnen, Club und Liga auswählen, alle Abo-App-Tabs durchklicken), impressum, datenschutz → **0 Verstöße** (Konsole + `securitypolicyviolation`-Events). Kontrollprobe: Ein injiziertes Inline-`style` und `<script>` wird gemeldet, der Mechanismus greift also. `element.style.*` aus `app.js` (CSSOM) fällt nicht unter `style-src`.

### Punkt 3 – `.gitignore`
Nur `.claude/settings.local.json`. Laut `git check-ignore` ist die Datei ignoriert, andere Pfade unter `.claude/` nicht.

### Punkt 4 – `.python-version`
Inhalt `3.12`. Es gibt keinen Widerspruch: `vercel.json` hat keine Runtime-Angabe, `pyproject.toml`/`uv.lock` behalten `requires-python = ">=3.12"`, `uv lock --check` ist OK.

### Punkt 6 – Dependabot
`github-actions` und `npm`, jeweils `/`, `monthly`, eine Gruppe (`patterns: ["*"]`) pro Ecosystem, Prefix `chore(deps)`, kein uv/pip. Schema-validiert (`check-jsonschema`, `vendor.dependabot`). Alle vier `uses:` haben das Format `<40-stellige SHA> # vX.Y.Z`, das Dependabot erkennt; es aktualisiert SHA und Kommentar gemeinsam.
Hinweis: `groups` gilt nur für *Version*-Updates. Dependabot-*Security*-Updates (falls im Repo aktiviert) kommen weiterhin als einzelne PRs, außer man ergänzt `applies-to: security-updates`.

### Punkt 7 – E2E in CI
- Neuer Job `e2e` in `test.yml`: Checkout ohne Credentials, `actions/setup-node` **v7.1.0** (neu, Node 24), `npm ci`, `npx playwright install --with-deps chromium`, `npx playwright test`, bei Fehlschlag `actions/upload-artifact` **v7.0.2** mit `playwright-report/`, `retention-days: 7`. Alles ist SHA-gepinnt. `permissions: contents: read` steht auf Workflow-Ebene und gilt für beide Jobs.
- Breaking Changes geprüft: setup-node v7 (ESM, geändertes `NODE_AUTH_TOKEN`-Verhalten, nicht genutzt), upload-artifact v7 (neuer optionaler `archive`-Input). Nichts davon betrifft uns.
- `playwright.config.js`: `retries`/`workers` wie vorgegeben. **Zusätzlich** (über die Vorgabe hinaus, bitte prüfen):
  - auf CI ein HTML-Reporter, weil der CI-Default-Reporter `dot` keinen `playwright-report/` schreibt und der Artifact-Upload sonst leer wäre;
  - `trace: "on-first-retry"`, damit der Report beim Retry einen Trace enthält.
  - Lokal ändert sich dadurch nichts (Reporter `list` wie bisher; Traces entstehen nur bei Retries, lokal ist `retries` 0).
- Lokal mit `CI=1` ausprobiert: grün 5/5. Mit absichtlich gebrochenem Assert gibt es einen Retry, Trace und HTML-Report entstehen. Den Workflow selbst auf GitHub konnte ich nicht ausführen (nicht gepusht).
- Kein Browser-/npm-Cache: `--with-deps` installiert die System-Pakete ohnehin bei jedem Lauf, und `npm ci` mit 4 Paketen ist schnell. Der Nutzen wäre gering, das Risiko veralteter Caches nicht.
- actionlint 1.7.12 **inkl. shellcheck**: 0 Fehler. Im ersten Lauf war shellcheck lokal nicht vorhanden und deshalb deaktiviert.

### Verifikation gesamt

| | Ergebnis |
|---|---|
| `pytest` | **144 passed** (143 + 1 neuer End-to-End-Test; der `rlsw-kickers`-Test ist umgestellt, nicht neu) |
| `npx playwright test --workers=1` | **5/5** |
| `npx playwright test` (Default-Worker) | **5/5** |
| `CI=1 npx playwright test` | **5/5** |
| `actionlint` (+ shellcheck) | 0 Fehler |
| `npm audit` | 0 vulnerabilities |
| ICS-Byte-Vergleich | **identisch** zu `main` (separater `main`-Worktree, alle Ligen + Renngruppen, 1.820 Events, ohne `DTSTAMP`) |
| `data/`, `public/data/`, `public/kalender.ics`, `robots.txt` | unverändert (`git diff main`) |

### Manuell in der Vercel-Preview prüfen
1. **Header:** `curl -sI https://<preview>/` sowie `/impressum.html`, `/api/calendar.ics?t=league:bl1:men` → alle fünf Header vorhanden, CSP nur als `…-Report-Only`.
2. **CSP-Report-Only:** DevTools-Konsole auf index/impressum/datenschutz, dabei Auswahl treffen und Abo-Tabs durchklicken → keine `[Report Only] Refused …`-Meldungen. Darauf achten, ob Vercel selbst etwas injiziert (Preview-Toolbar/Feedback-Widget, Analytics). Das würde Verstöße melden, die lokal nicht auftreten, und gehört vor einem späteren Enforce in die CSP oder abgeschaltet.
3. **ICS-Download:** `curl -sI …/api/calendar.ics?t=…` und `…/kalender.ics` → `Content-Type: text/calendar…` unverändert. Außerdem ein bestehendes Abo in einem Kalender-Client (Apple/Google) aktualisieren lassen: keine Duplikate, gleicher Kalendername.
4. **Python-Version:** Im Build-Log der Function prüfen, dass Vercel 3.12 aus `.python-version` übernimmt. Falls Vercel 3.12 nicht (mehr) anbietet, bricht der Build bzw. es gibt eine Warnung. Dann `.python-version` anpassen und CI nachziehen.
5. **Erster CI-Lauf** nach dem Push: Job `e2e` grün, Laufzeit plausibel (Browser-Installation dominiert).
