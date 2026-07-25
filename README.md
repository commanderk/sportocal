# sportocal

Ein Sport-Kalender (Fußball + Radsport) mit personalisierbarem `.ics`-Abo und einer kleinen Website – gehostet auf Vercel (Hobby-Plan): eine statische Seite unter `public/` und eine Python-Serverless-Function (`api/calendar.ics.py`) für den personalisierten Kalenderlink, aus demselben Repo und Deploy. Die Datenaktualisierung läuft weiterhin wöchentlich im Hintergrund über GitHub Actions (`scripts/fetch_*.py`); jeder daraus entstehende Commit löst automatisch ein Vercel-Redeploy aus, wodurch die Function wieder aktuelle Daten aus dem Deployment-Bundle liest. Kein Login, kein Cookie, kein Server im klassischen Sinn, kein API-Key. Das Frontend (`public/index.html`/`app.js`) zeigt aktuell noch die volle, ungefilterte Terminliste aller ~65 Vereine – die Multi-Select-Auswahl-UI, die daraus einen personalisierten Abo-Link baut, ist als eigene Phase geplant.

## Was drin ist

**Fußball** (Quelle: [OpenLigaDB](https://api.openligadb.de)), alle Vereine aus:
- 1. Bundesliga, 2. Bundesliga, 3. Liga (Herren)
- Frauen-Bundesliga, 2. Frauen-Bundesliga
- Regionalliga Südwest – **nur** Stuttgarter Kickers (bewusst kein voller Liga-Ausbau)
- DFB-Pokal (Herren) für alle oben genannten Vereine, die daran teilnehmen

**DFB-Pokal der Frauen:** aktuell (Stand 2026) führt OpenLigaDB dafür keine eigene Liga – die Quelle ist trotzdem in `config.json` konfiguriert (`dfb-pokal-women`) und wird bei jedem Lauf versucht; liefert sie weiterhin nichts, wird das nur geloggt, nicht als Fehler behandelt. Taucht die Liga dort später auf, greift sie ohne Codeänderung.

**Regionalliga Südwest – Fallback-Quelle:** OpenLigaDB hat für diese Liga aktuell (Stand 2026) keine gepflegten Daten – der letzte vorhandene Datensatz stammt aus der Saison 2016/17 (echte Lücke in der freien Datenquelle, keine fehlerhafte Fuzzy-Match; veraltete Season-Treffer werden aktiv ignoriert statt Jahre alte Spielpläne anzuzeigen). `fetch_football.py` versucht deshalb zuerst OpenLigaDB und weicht bei dieser Liga automatisch auf die offizielle Spielplan-Seite der Stuttgarter Kickers aus (`stuttgarter-kickers.de/team/spielplan`, robots.txt erlaubt Crawling, server-rendertes HTML). Sobald OpenLigaDB die Liga wieder pflegt, greift wieder die generische API-Quelle. Einschränkungen der Fallback-Quelle: sie kennt keine offizielle Spieltag-Nummer (wird chronologisch approximiert) und ist an das aktuelle Markup der Vereins-Website gebunden – ändert sich das Seiten-Layout grundlegend, greift wieder nur die Warnung statt eines Absturzes.

**Radsport** (Quelle: Wikipedia, siehe Begründung unten):
- Tour de France, Giro d'Italia, Vuelta a España – alle Einzeletappen (Kernumfang)
- ADAC Cyclassics Hamburg, Sparkassen Münsterland Giro, Deutschland Tour – bewusste Erweiterung, kein Rückbau geplant

## Warum Wikipedia für Radsport?

Es gibt keine freie, gepflegte API wie OpenLigaDB für Radsport. Geprüft und verworfen wurden:
- **ProCyclingStats**: keine dokumentierte Erlaubnis fürs Scraping, aggressives Blocking.
- **Offizielle Renn-Websites**: keine einheitliche Struktur über verschiedene Rennen hinweg – jede Website bräuchte einen eigenen Parser, würde die "ohne Umbau erweiterbar"-Anforderung verletzen.

**Wikipedia** (CC BY-SA, frei nutzbar) veröffentlicht für jede Ausgabe einen eigenen Artikel:
- Eintägige Rennen (Cyclassics, Münsterland Giro) haben eine Infobox mit `date = ...`.
- Mehrtägige Rennen (Grand Tours, Deutschland Tour) haben eine "Route and stages"/"Schedule"-Wikitabelle mit einer Zeile pro Etappe.

`scripts/fetch_cycling.py` parst beide Formate direkt aus dem Wikitext über die MediaWiki-API (`action=parse`).

**Bekannte Einschränkung:** Wikipedia legt den Jahres-Artikel für kleinere Rennen (Cyclassics, Münsterland Giro, Deutschland Tour) oft erst kurz vor dem Termin an – manchmal erst wenige Wochen vorher. Existiert der Artikel für das aktuelle/nächste Jahr noch nicht, loggt das Script eine Warnung und lässt den letzten bekannten Snapshot unverändert; sobald der Artikel erscheint, wird er beim nächsten wöchentlichen Lauf automatisch aufgenommen. **Rund um Köln** wurde bewusst nicht aufgenommen: es gibt dort keine jahresspezifischen Wikipedia-Artikel, nur eine Gewinner-Liste ohne Termine für kommende Ausgaben.

## Datenmodell

Ein generisches, sportartübergreifendes Event-Schema (siehe `scripts/common.py` und die `data/*.json`-Snapshots). Der Kalender-Titel wird **nicht** gespeichert, sondern von `format_event_title()` in `scripts/common.py` zur Build-Zeit aus den Rohdaten generiert – ein Format-Wechsel braucht dadurch keine Datenmigration:

```json
{
  "id": "football-bl1-83457",
  "sport": "football",
  "competition": "Bundesliga",
  "gender": "men",
  "round": "Spieltag 34",
  "start": "2027-05-22T13:30:00Z",
  "timeConfirmed": true,
  "location": "Stadion, Stadt",
  "homeTeamId": "1-fsv-mainz-05",
  "homeTeamName": "1. FSV Mainz 05",
  "homeTeamLogo": "https://...",
  "awayTeamId": "vfb-stuttgart",
  "awayTeamName": "VfB Stuttgart",
  "awayTeamLogo": "https://..."
}
```

`homeTeamId`/`awayTeamId` verweisen auf `config/clubs.json` (siehe unten) und sind `null`, wenn der Verein dort nicht geführt wird – kommt bei frühen DFB-Pokal-Runden vor (Amateurvereine) und übergangsweise bei Ligen, deren aktuelle Saison bei OpenLigaDB noch nicht befüllt ist (dann greift der Fetch auf die letzte befüllte Saison zurück, deren Kader leicht abweichen kann). `homeTeamName`/`awayTeamName` sind in jedem Fall gesetzt und dienen als Klartext-Fallback für den Titel, wenn keine Club-ID aufgelöst werden konnte.

Radsport-Events haben statt `homeTeamId`/… ein optionales `route`-Feld (`start`/`finish`/`type`) – neue Sportarten können beliebige eigene Zusatzfelder mitbringen, ohne `build_ics.py`, `build_site_data.py` oder die Website anzufassen, da diese nur die gemeinsamen Basisfelder auswerten.

`start` ist entweder ein volles ISO-8601-UTC-Datum/Zeit (Fußball, `Z`-Suffix) oder ein reines Datum `YYYY-MM-DD` (Radsport – Uhrzeit unbekannt). `timeConfirmed: false` bedeutet: Uhrzeit ist Platzhalter/unbekannt, die ICS-Datei und die Website zeigen den Termin dann als ganztägig bzw. mit Hinweis-Badge.

**Saison-Cut:** Innerhalb einer Saison wird nie gefiltert (vergangene und zukünftige Termine bleiben beide im Snapshot). Der Cut auf eine neue Saison passiert implizit dadurch, dass `fetch_football.py` bei jedem Lauf die neueste befüllte Saison sucht und den kompletten Snapshot durch deren Daten ersetzt – kein zusätzlicher Zeit-Filter nötig, Website und Kalender können dadurch nicht auseinanderlaufen.

## Vereins-Datenmodell (`config/clubs.json`)

Ein Eintrag pro Verein (nicht pro Team) mit Farb- und Liga-Zuordnung für Herren/Damen:

```json
{
  "id": "fc-bayern-muenchen",
  "name": "FC Bayern München",
  "shortName": "FCB",
  "colorHex": "#DC052D",
  "colorPalette": "red",
  "logo": null,
  "teams": {
    "men": { "league": "Bundesliga", "openligadbShortcut": "bl1", "openligadbTeamName": "FC Bayern München" },
    "women": { "league": "Frauen-Bundesliga", "openligadbShortcut": "ffb1", "openligadbTeamName": "FC Bayern München Frauen" }
  }
}
```

`colorPalette` ist einer von 9 Werten (`red, orange, yellow, green, blue, purple, black, white, brown`) und steuert das Emoji im generierten Kalendertitel: Quadrat = Herren (🟥🟧🟨🟩🟦🟪⬛⬜🟫), Kreis = Damen (🔴🟠🟡🟢🔵🟣⚫⚪🟤). `colorHex` ist für spätere UI-Chips gedacht (noch ungenutzt, Frontend-Rework folgt in einer späteren Phase). Bei mehrfarbigen Vereinswappen wurde die auffälligste/bekannteste Farbe gewählt, nicht zwingend die laut Wikipedia-Infobox zuerst genannte.

65 Vereine sind erfasst: alle Clubs aus 1./2./3. Liga, Frauen-Bundesliga, 2. Frauen-Bundesliga (Männer- und Frauen-Abteilung desselben Vereins sind ein gemeinsamer Eintrag) sowie Stuttgarter Kickers. Zweitmannschaften (z. B. „VfB Stuttgart II", „1. FC Köln II") haben eigene Einträge mit denselben Vereinsfarben wie die erste Mannschaft, da sie parallel in einer anderen Liga spielen und einzeln abonnierbar sein sollen.

`build_club_indexes()` in `scripts/common.py` baut daraus eine Namens-Lookup-Tabelle (exakter OpenLigaDB-Teamname + normalisierter Vereinsname), mit der `fetch_football.py` jeden Spiel-Teilnehmer auf eine Club-ID auflöst.

## Projektstruktur

```
config.json                  # Liga-Quellen (Fußball) + Rennen (Radsport) – hier erweitern
config/
  clubs.json                  # Vereins-Mapping: Farben, Kurzname, Liga-Zuordnung je Geschlecht
scripts/
  common.py                  # Event-Modell, Club-Lookup, Titel-Formatter, ICS-Rendering, Snapshot-Diff, HTTP-/Wikitext-Helper
  fetch_football.py          # OpenLigaDB, Fuzzy-Match der Liga-Shortcuts, Club-ID-Auflösung
  fetch_cycling.py           # Wikipedia-Wikitext-Parser
  build_ics.py                # data/*.json + config/clubs.json -> public/kalender.ics (unfilterierter Kombi-Feed)
  build_site_data.py          # data/*.json -> public/data/events.json
api/
  calendar.ics.py             # Vercel Python Function: personalisierte /api/calendar.ics
data/                         # ein JSON-Snapshot pro Liga-Quelle (Diff-Basis), z.B. football-bl1.json
public/                       # Vercel Static Root
  index.html / app.js / style.css
  kalender.ics                # generierte, kombinierte Kalenderdatei (Interims-Feed, siehe unten)
  data/events.json            # generierte, kombinierte Website-Daten
vercel.json                   # Vercel-Projektkonfiguration
.github/workflows/update.yml # wöchentlicher Cron + manueller Trigger
```

**Wichtig:** `public/` ist der Vercel Static Root. Nur was dort liegt, ist per HTTP erreichbar – deshalb erzeugt `build_site_data.py` eine kombinierte Kopie unter `public/data/events.json`, obwohl die Roh-Snapshots in `data/` liegen. `data/` und `config/` sind trotzdem Teil des Deployments (nur nicht direkt per URL erreichbar) und genau deshalb kann `api/calendar.ics.py` sie serverseitig lesen.

## Personalisierter Kalenderlink (`/api/calendar.ics`)

Zustandslos: die Auswahl steckt komplett in der URL, kein serverseitiger Speicher, kein Cookie.

```
GET /api/calendar.ics?t=<clubId>:men,<clubId>:women,race:<raceId>,...
```

- `<clubId>:men` / `<clubId>:women` – Club-ID aus `config/clubs.json` + Geschlecht, z. B. `fc-bayern-muenchen:men`
- `race:<raceId>` – Renn-ID aus `config.json` (`cycling.races`), z. B. `race:tour-de-france`

Beispiel: `?t=fc-bayern-muenchen:men,stuttgarter-kickers:men,race:tour-de-france`

Die Function liest `data/*.json` + `config/clubs.json` aus dem Deployment-Bundle, filtert und generiert die ICS-Datei bei jedem Aufruf neu (kein Caching, `Cache-Control: no-store`) – automatische Kalender-Refreshes bekommen dadurch immer den Stand des letzten wöchentlichen Redeploys. Im generierten Titel bekommt nur ein ausgewählter Verein sein Farb-/Form-Emoji; der Gegner erscheint auch dann als Klartext, wenn er selbst ein bekannter Verein ist (Ausnahme: spielen zwei ausgewählte Vereine gegeneinander, bekommen beide ihr Emoji). Unbekannte oder nicht mehr existierende Club-/Renn-IDs im Parameter werden stillschweigend ignoriert (führt zu einem entsprechend kleineren, aber gültigen Kalender) statt eines Fehlers – ein alter, bereits abonnierter Link soll nie hart brechen. Fehlt der Parameter `t` komplett oder ist leer, antwortet die Function mit `400`.

Enthalten ist immer die komplette aktuelle Saison (vergangene und zukünftige Termine); der Cut auf eine neue Saison passiert implizit beim wöchentlichen Fetch (siehe Datenmodell oben), nicht in dieser Function.

## Warum Liga-Shortcuts nicht hartkodiert sind

OpenLigaDB ist ein Community-Projekt. `bl1` (1. Bundesliga) ist stabil, aber Shortcuts für Regionalliga Südwest und die Frauen-Ligen ändern sich von Saison zu Saison (z.B. `fbl2`, `ffb2`, `bl2f` für dieselbe Liga in unterschiedlichen Jahren) oder werden gar nicht gepflegt. `fetch_football.py` ruft deshalb immer zuerst `getavailableleagues` ab und matcht den aktuellen Shortcut per Fuzzy-Match auf den Liga-Namen (Keyword-Listen in `config.json`, z.B. `["bundesliga", "frauen", "2"]`). Ligen, deren neuester Datensatz älter als ein Jahr ist, werden als "nicht mehr gepflegt" behandelt und übersprungen (mit Log-Hinweis) statt veraltete Daten anzuzeigen.

## Lokal ausführen

```bash
pip install -r requirements.txt
python scripts/fetch_football.py
python scripts/fetch_cycling.py
python scripts/build_ics.py
python scripts/build_site_data.py

# Website lokal ansehen:
cd public && python3 -m http.server 8000
# -> http://localhost:8000

# Mit Vercel CLI (Website + /api/calendar.ics zusammen):
vercel dev
# -> http://localhost:3000/api/calendar.ics?t=fc-bayern-muenchen:men
```

## Erweitern

Ein neues Rennen kommt allein durch einen neuen Eintrag in `config.json` dazu. Eine neue Liga (z. B. eine weitere Regionalliga-Staffel) braucht einen neuen Eintrag in `config.json` unter `football.leagues` (mit passendem `scope`: `full`, `club-filter` oder `cup`) plus die entsprechenden Vereine in `config/clubs.json` – kein Umbau von `fetch_football.py` nötig. Ein neuer Verein in einer bereits erfassten Liga kommt automatisch dazu, sobald er bei OpenLigaDB auftaucht; für einen sauber aufgelösten (statt als Klartext angezeigten) Namen braucht er zusätzlich einen Eintrag in `config/clubs.json`. Eine komplett neue Sportart braucht ein neues `fetch_<sportart>.py`, das Events im gleichen Basisschema in `data/<quelle>.json` schreibt, plus einen Fall in `format_event_title()` (`scripts/common.py`); `build_ics.py`, `build_site_data.py` und die Website müssen dafür nicht angefasst werden.

## Vercel einrichten (einmalig)

1. Auf [vercel.com](https://vercel.com) ein neues Projekt aus diesem GitHub-Repo anlegen (eigener Hobby-Plan-Slot, unabhängig von anderen Projekten). Vercel erkennt `api/calendar.ics.py` automatisch als Python Function und `public/` als Static Root (siehe `vercel.json`) – kein Build-Schritt nötig.
2. Damit die Function `data/*.json` + `config/clubs.json` sehen kann, müssen diese Teil des Git-Repos sein (sind sie bereits) – Vercel bündelt beim Deploy alles, was zur Build-Zeit erreichbar ist.
3. Fertig – die Seite liegt danach unter `https://<projekt>.vercel.app/`, der personalisierte Kalenderlink unter `https://<projekt>.vercel.app/api/calendar.ics?t=...` (bzw. `webcal://...`), der unfiltrierte Interims-Feed unter `/kalender.ics`.

Der Workflow `.github/workflows/update.yml` läuft automatisch jeden Montag 06:00 UTC und lässt sich zusätzlich manuell über den Tab „Actions" → „Update sportocal calendar" → „Run workflow" anstoßen. Jeder dadurch entstehende Commit auf dem verbundenen Branch löst automatisch ein Vercel-Redeploy aus (Vercels GitHub-Integration, kein Zutun nötig, sobald das Projekt einmal verbunden ist).

