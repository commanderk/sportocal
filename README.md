# sportocal

Ein kombinierter Sport-Kalender (Fußball + Radsport) als `.ics`-Abo und als kleine statische Website – gehostet auf GitHub Pages, wöchentlich automatisch aktualisiert über GitHub Actions. Kein Server, kein API-Key.

## Was drin ist

**Fußball** (Quelle: [OpenLigaDB](https://api.openligadb.de)):
- Mainz 05 (Herren) – Bundesliga + DFB-Pokal
- Stuttgarter Kickers – Regionalliga Südwest + DFB-Pokal
- Mainz 05 (Frauen) – 2. Bundesliga Frauen

**Regionalliga Südwest – Fallback-Quelle:** OpenLigaDB hat für diese Liga aktuell (Stand 2026) keine gepflegten Daten – der letzte vorhandene Datensatz stammt aus der Saison 2016/17 (echte Lücke in der freien Datenquelle, keine fehlerhafte Fuzzy-Match; veraltete Season-Treffer werden aktiv ignoriert statt Jahre alte Spielpläne anzuzeigen). `fetch_football.py` versucht deshalb zuerst OpenLigaDB und weicht bei dieser Liga automatisch auf die offizielle Spielplan-Seite der Stuttgarter Kickers aus (`stuttgarter-kickers.de/team/spielplan`, robots.txt erlaubt Crawling, server-rendertes HTML). Sobald OpenLigaDB die Liga wieder pflegt, greift wieder die generische API-Quelle. Einschränkungen der Fallback-Quelle: sie kennt keine offizielle Spieltag-Nummer (wird chronologisch approximiert) und ist an das aktuelle Markup der Vereins-Website gebunden – ändert sich das Seiten-Layout grundlegend, greift wieder nur die Warnung statt eines Absturzes.

**Radsport** (Quelle: Wikipedia, siehe Begründung unten):
- Tour de France, Giro d'Italia, Vuelta a España – alle Einzeletappen
- ADAC Cyclassics Hamburg, Sparkassen Münsterland Giro, Deutschland Tour

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

Ein generisches, sportartübergreifendes Event-Schema (siehe `scripts/common.py` und die `data/*.json`-Snapshots):

```json
{
  "id": "football-mainz05-herren-83457",
  "sport": "football",
  "competition": "Bundesliga",
  "round": "Spieltag 34",
  "title": "🟥 MZ05 - VfB Stuttgart – Bundesliga – Spieltag 34",
  "start": "2027-05-22T13:30:00Z",
  "timeConfirmed": true,
  "location": "Stadion, Stadt",
  "participants": { "home": {...}, "away": {...} },
  "homeAway": "home"
}
```

Radsport-Events haben statt `participants` ein optionales `route`-Feld (`start`/`finish`/`type`) – neue Sportarten können beliebige eigene Zusatzfelder mitbringen, ohne `build_ics.py`, `build_site_data.py` oder die Website anzufassen, da diese nur die gemeinsamen Basisfelder auswerten.

`start` ist entweder ein volles ISO-8601-UTC-Datum/Zeit (Fußball, `Z`-Suffix) oder ein reines Datum `YYYY-MM-DD` (Radsport – Uhrzeit unbekannt). `timeConfirmed: false` bedeutet: Uhrzeit ist Platzhalter/unbekannt, die ICS-Datei und die Website zeigen den Termin dann als ganztägig bzw. mit Hinweis-Badge.

## Projektstruktur

```
config.json                  # Teams/Ligen/Rennen – hier erweitern
scripts/
  common.py                  # Event-Modell, Snapshot-Diff, HTTP-/Wikitext-Helper
  fetch_football.py          # OpenLigaDB, Fuzzy-Match der Liga-Shortcuts
  fetch_cycling.py           # Wikipedia-Wikitext-Parser
  build_ics.py                # data/*.json -> docs/kalender.ics
  build_site_data.py          # data/*.json -> docs/data/events.json
data/                         # ein JSON-Snapshot pro Quelle (Diff-Basis)
docs/                         # GitHub Pages Root
  index.html / app.js / style.css
  kalender.ics                # generierte, kombinierte Kalenderdatei
  data/events.json            # generierte, kombinierte Website-Daten
.github/workflows/update.yml # wöchentlicher Cron + manueller Trigger
```

**Wichtig:** `docs/` ist der GitHub-Pages-Root. Nur was dort liegt, ist per HTTP erreichbar – deshalb erzeugt `build_site_data.py` eine kombinierte Kopie unter `docs/data/events.json`, obwohl die Roh-Snapshots in `data/` liegen.

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
cd docs && python3 -m http.server 8000
# -> http://localhost:8000
```

## Erweitern

Ein neuer Verein/Liga/Rennen kommt allein durch einen neuen Eintrag in `config.json` dazu – keine Code-Änderung nötig, solange die Quelle (OpenLigaDB bzw. Wikipedia im gleichen Format) passt. Eine komplett neue Sportart braucht ein neues `fetch_<sportart>.py`, das Events im gleichen Basisschema in `data/<quelle>.json` schreibt; `build_ics.py`, `build_site_data.py` und die Website müssen dafür nicht angefasst werden.

## GitHub Pages einrichten (einmalig)

1. Repo auf GitHub anlegen, dieses Verzeichnis pushen.
2. Repo-Einstellungen → **Pages** → Source: „Deploy from a branch" → Branch `main`, Ordner `/docs`.
3. Fertig – die Seite liegt danach unter `https://<user>.github.io/<repo>/`, das Kalender-Abo unter derselben URL + `/kalender.ics` (bzw. `webcal://...`).

Der Workflow `.github/workflows/update.yml` läuft automatisch jeden Montag 06:00 UTC und lässt sich zusätzlich manuell über den Tab „Actions" → „Update sportocal calendar" → „Run workflow" anstoßen.

