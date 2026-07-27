# sportocal

Ein Sport-Kalender (Fußball + Radsport) mit personalisierbarem `.ics`-Abo und einer kleinen Website – gehostet auf Vercel (Hobby-Plan): eine statische Seite unter `public/` und eine Python-Serverless-Function (`api/calendar_ics.py`) für den personalisierten Kalenderlink, aus demselben Repo und Deploy. Die Datenaktualisierung läuft weiterhin wöchentlich im Hintergrund über GitHub Actions (`scripts/fetch_*.py`); jeder daraus entstehende Commit löst automatisch ein Vercel-Redeploy aus, wodurch die Function wieder aktuelle Daten aus dem Deployment-Bundle liest. Kein Login, kein Cookie, kein Server im klassischen Sinn, kein API-Key.

Das Frontend (`public/index.html`/`app.js`, Basis: ein Claude-Design-Entwurf) lässt Nutzer Fußballvereine (gruppiert nach Liga) und Radsport-Rennen per Multi-Select auswählen; ausgewählte Elemente erscheinen als farbige, entfernbare Chips in der jeweiligen Vereinsfarbe. Ohne Auswahl zeigt die Seite eine ungefilterte Vorschau aller Termine; sobald mindestens ein Verein oder Rennen ausgewählt ist, schaltet sich die Abo-Leiste frei: ein `webcal://`-Button ("Kalender abonnieren") plus die reine `https://`-URL zum Kopieren (für Google Calendar, das `webcal://` nicht zuverlässig unterstützt) und eine Klartext-Bestätigungszeile ("Dein Kalender enthält: ..."). Kein Download-Button -- eine heruntergeladene Datei würde sich nie aktualisieren.

## Was drin ist

**Fußball** (Quelle: [OpenLigaDB](https://api.openligadb.de)), alle Vereine aus:
- 1. Bundesliga, 2. Bundesliga, 3. Liga (Herren)
- Frauen-Bundesliga, 2. Frauen-Bundesliga
- Regionalliga Südwest – **nur** Stuttgarter Kickers (bewusst kein voller Liga-Ausbau)
- DFB-Pokal (Herren) für alle oben genannten Vereine, die daran teilnehmen

**DFB-Pokal der Frauen:** aktuell (Stand 2026) führt OpenLigaDB dafür keine eigene Liga – die Quelle ist trotzdem in `config.json` konfiguriert (`dfb-pokal-women`) und wird bei jedem Lauf versucht; liefert sie weiterhin nichts, wird das nur geloggt, nicht als Fehler behandelt. Taucht die Liga dort später auf, greift sie ohne Codeänderung.

**Regionalliga Südwest – Fallback-Quelle:** OpenLigaDB hat für diese Liga aktuell (Stand 2026) keine gepflegten Daten – der letzte vorhandene Datensatz stammt aus der Saison 2016/17 (echte Lücke in der freien Datenquelle, keine fehlerhafte Fuzzy-Match; veraltete Season-Treffer werden aktiv ignoriert statt Jahre alte Spielpläne anzuzeigen). `fetch_football.py` versucht deshalb zuerst OpenLigaDB und weicht bei dieser Liga automatisch auf die offizielle Spielplan-Seite der Stuttgarter Kickers aus (`stuttgarter-kickers.de/team/spielplan`, robots.txt erlaubt Crawling, server-rendertes HTML). Sobald OpenLigaDB die Liga wieder pflegt, greift wieder die generische API-Quelle. Einschränkungen der Fallback-Quelle: sie kennt keine offizielle Spieltag-Nummer (wird chronologisch approximiert) und ist an das aktuelle Markup der Vereins-Website gebunden – ändert sich das Seiten-Layout grundlegend, greift wieder nur die Warnung statt eines Absturzes.

**Radsport** (Quelle: Wikipedia-Scraper oder manuelle CSV-Pflege, siehe Begründung unten):
- Tour de France, Giro d'Italia, Vuelta a España – alle Einzeletappen (Kernumfang)
- ADAC Cyclassics Hamburg, Sparkassen Münsterland Giro, Deutschland Tour – bewusste Erweiterung, kein Rückbau geplant
- 17 weitere Etappenrennen (Männer-UCI-WorldTour + Frauen-Grand-Tour-Kandidaten/UCI-WorldTour, siehe `scripts/tools/race_candidates.json`) als `"source": "manual"`-Einträge – Config-Gerüst steht, Etappendaten kommen über `data/manual/stage-race.csv` nach und nach dazu (siehe unten)

## Warum Wikipedia für Radsport?

Es gibt keine freie, gepflegte API wie OpenLigaDB für Radsport. Geprüft und verworfen wurden:
- **ProCyclingStats**: keine dokumentierte Erlaubnis fürs Scraping, aggressives Blocking.
- **Offizielle Renn-Websites**: keine einheitliche Struktur über verschiedene Rennen hinweg – jede Website bräuchte einen eigenen Parser, würde die "ohne Umbau erweiterbar"-Anforderung verletzen.

**Wikipedia** (CC BY-SA, frei nutzbar) veröffentlicht für jede Ausgabe einen eigenen Artikel:
- Eintägige Rennen (Cyclassics, Münsterland Giro) haben eine Infobox mit `date = ...`.
- Mehrtägige Rennen (Grand Tours, Deutschland Tour) haben eine "Route and stages"/"Schedule"-Wikitabelle mit einer Zeile pro Etappe.

`scripts/fetch_cycling.py` parst beide Formate direkt aus dem Wikitext, abgerufen über `action=query&prop=revisions` (der reine Rohtext-Abruf, ohne Wikipedias Seiten-Parser zu triggern). Der Existenz-Check läuft über das noch leichtere `action=query&prop=info` (ganz ohne Content-Transfer). Beides folgt der MediaWiki-API-Etikette (https://www.mediawiki.org/wiki/API:Etiquette), die für reine Rohtext-Abrufe explizit von `action=parse` abrät, sowie einem eigenen User-Agent mit Projektname und Kontakt-URL. Da `action=query&prop=revisions` – anders als `action=parse` – keinen `section=`-Parameter kennt, bildet `extract_section()` in `fetch_cycling.py` die Sektionsauswahl lokal nach; nur die Suche nach der Etappentabellen-Sektion selbst (`action=parse&prop=sections`) bleibt auf dem alten Endpunkt, da es dafür keinen 1:1-Ersatz gibt.

**Bekannte Einschränkung:** Wikipedia legt den Jahres-Artikel für kleinere Rennen (Cyclassics, Münsterland Giro, Deutschland Tour) oft erst kurz vor dem Termin an – manchmal erst wenige Wochen vorher. Existiert der Artikel für das aktuelle/nächste Jahr noch nicht, loggt das Script eine Warnung und lässt den letzten bekannten Snapshot unverändert; sobald der Artikel erscheint, wird er beim nächsten wöchentlichen Lauf automatisch aufgenommen. **Rund um Köln** wurde bewusst nicht aufgenommen: es gibt dort keine jahresspezifischen Wikipedia-Artikel, nur eine Gewinner-Liste ohne Termine für kommende Ausgaben.

## Radsport-Taxonomie: Gender, Tier, Begriffe

Jedes Rennen unter `cycling.races` in `config.json` trägt neben `type` (`one-day`/`stage-race`, rein strukturell) drei redaktionelle Felder: `gender` (`men`/`women`), `tier` (`grand-tour`/`uci-worldtour`/`uci-proseries`/`regional`) und optional `country` (z. B. `DE`, quer zu den Tiers – für eine "wichtige deutsche Rennen"-Gruppierung, aktuell nur als Datenfeld, noch ohne eigene UI). Die Auswahl-UI gruppiert Rennen im Radsport-Selector nach `tier` (Reihenfolge: Grand Tour, UCI WorldTour, UCI ProSeries, Regional) und bietet einen Männer/Frauen/Alle-Filter an, der sowohl die Rennliste im Picker als auch die angezeigten Termine einschränkt.

Begriffsklärung, falls die UCI-Kürzel in Rennnamen oder Quellen auftauchen:

| Begriff | Bedeutung | Achse |
|---|---|---|
| `ME` / `WE` | Men Elite / Women Elite | Kategorie (Alter/Startberechtigung), nicht Renn-Tier |
| `1.` / `2.` | Eintagesrennen / Etappenrennen | Renntyp |
| `UWT` / `WWT` | UCI (Women's) WorldTour, höchste Stufe | Tier |
| `Pro` | UCI ProSeries, zweithöchste Stufe | Tier |
| `.1` / `.2` | Continental Circuits, `.1` > `.2` | Tier |
| `CM` / `JOJ` | Weltmeisterschaft / Jugend-Olympia | eigenes System, kein Tier |
| "Grand Tour" | informeller Begriff, kein UCI-Code | redaktionelle Kategorie |

**Vorbehalt bei den Frauen-"Grand Tours":** Tour de France Femmes, Giro d'Italia Women und Vuelta España Femenina laufen hier als `tier: "grand-tour"`, weil sie inhaltlich das Pendant zu den Männer-Grand-Tours sind und in der Presse auch so behandelt werden – sie erfüllen aber (Stand heute) nicht die offizielle UCI-Definition eines Grand Tours (dauern 7–8 statt 3 Wochen). Die Einordnung ist also bewusst redaktionell, nicht UCI-formal.

## Wie wird für ein neues Rennen die Quelle entschieden?

Bevor ein neues Rennen einen scraper-basierten Eintrag in `config.json` bekommt, läuft `scripts/tools/verify_race_sources.py` – ein manuelles, nicht in `update.yml` eingebundenes Tool (Aufruf: `python scripts/tools/verify_race_sources.py`), das für eine Kandidatenliste (`scripts/tools/race_candidates.json`) prüft, ob Wikipedia für das aktuelle und das nächste Jahr einen Artikel mit parsbarer Etappentabelle liefert – dieselbe Prüfung, die für Deutschland Tour schon einmal manuell gemacht wurde, jetzt als wiederholbarer Batch-Lauf für beliebig viele Kandidaten auf einmal. Das Tool schreibt nur einen Report (`scripts/tools/verification-report.md`, nicht eingecheckt) und ändert nie `config.json` oder `data/*.json` selbst – das Übernehmen einer Empfehlung bleibt ein bewusster, manueller letzter Schritt.

Klassifizierung pro Rennen und Jahr: `ok` (Artikel + Etappentabelle sauber geparst), `article-missing` (kein Jahresartikel), `unparseable` (Artikel da, Tabelle aber nicht extrahierbar, z. B. bei Wikidata-Vorlagen), `title-unclear` (der Wikipedia-Titel lässt sich nicht zuverlässig aus dem Rennnamen raten, z. B. bei wechselnden Sponsorennamen – wird ohne Netzwerk-Aufruf direkt als "manuell prüfen" markiert). Empfehlung: **Scraper**, wenn beide geprüften Jahre `ok` sind, sonst **Manuell** (CSV-Sheet) – schon ein einziger Fehlschlag würde im Betrieb einen wöchentlichen `warn()`-Fall erzeugen, den dieses Verfahren bewusst vermeidet. Der Prozess ist der Standardweg für **jedes** künftige Rennen, nicht nur für eine einmalige Kandidatenliste, und wird bei Bedarf erneut angestoßen (z. B. einmal jährlich vor Saisonbeginn) – kein automatisches Hochstufen von "manuell" zu "Scraper", falls später doch ein Artikel auftaucht.

**Die 17 als "Manuell" verifizierten Rennen** (9 Männer-UCI-WorldTour-Etappenrennen + 3 Frauen-Grand-Tour-Kandidaten + 5 weitere Frauen-UCI-WorldTour-Etappenrennen – die komplette Liste aus `scripts/tools/race_candidates.json`) laufen über dieselbe CSV-Pipeline, die für die deutschen Regional-/ProSeries-Rennen vorgesehen ist: ein Eintrag in `config.json` mit `"source": "manual"` (kein `wikipediaTitleTemplate`) sagt `fetch_cycling.py`, dieses Rennen zu überspringen; `scripts/build_manual_cycling.py` liest stattdessen `data/manual/stage-race.csv` (Spalten `race_id,year,stage_label,date,start,finish,type`, Datum als `YYYY-MM-DD`, `type` muss einer der Werte aus `common.STAGE_TYPES` sein) und schreibt denselben additiven Snapshot (`merge_events()`, siehe oben) unter `data/cycling-<race-id>.json` – für `build_ics.py`/`build_site_data.py` nicht unterscheidbar von einem gescrapten Rennen. Eine fehlerhafte Zeile (unbekannter `type`, fehlendes Pflichtfeld, kaputtes Datum) wird geloggt und übersprungen, nicht zum Absturz des ganzen Laufs. Auch dieses Skript ist **nicht** Teil von `update.yml` – Aufruf bei Bedarf: `python scripts/build_manual_cycling.py`, nachdem die CSV-Datei gepflegt wurde.

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

**Saison-Cut (nur Fußball):** Innerhalb einer Saison wird nie gefiltert (vergangene und zukünftige Termine bleiben beide im Snapshot). Der Cut auf eine neue Saison passiert implizit dadurch, dass `fetch_football.py` bei jedem Lauf die neueste befüllte Saison sucht und den kompletten Snapshot durch deren Daten ersetzt – kein zusätzlicher Zeit-Filter nötig, Website und Kalender können dadurch nicht auseinanderlaufen. Das ist hier strukturell nötig, weil Vereine zwischen Saisons die Liga wechseln (Auf-/Abstieg) und die Zuordnung in `config/clubs.json` pro Saison neu stimmen muss.

**Additiver Merge (nur Radsport):** `fetch_cycling.py` hat keine solche Saison-Kopplung – ein Rennen wird über seine eigene `race_id` abgerufen, unabhängig von einer Liga-Zuordnung. Ein neuer Lauf **ersetzt** den Snapshot deshalb nicht, sondern merged additiv (`merge_events()`): neue Renn-IDs kommen dazu, bestehende IDs werden aktualisiert, aber keine alte ID wird je entfernt, nur weil sie in diesem Lauf nicht erneut geliefert wurde. Vergangene Ausgaben bleiben dadurch dauerhaft in ICS-Datei und Website erhalten, statt beim nächsten Lauf zu verschwinden. Das Datenvolumen bleibt dabei überschaubar (aktuell ~6 Rennen, auch bei vollem Ausbau auf ~39 Config-Einträge nur wenige Termine mehr pro Jahr), daher gibt es dafür bewusst kein Zeitfenster-Limit in Web-Ansicht oder ICS. Da dadurch mehrere Ausgaben desselben Eintagesrennens gleichzeitig sichtbar sein können, hängt `eventDisplayTitle()` in `public/app.js` in diesem Fall die Jahreszahl an den Zeilentitel an (z. B. "Cyclassics Hamburg 2026"), sobald mehr als eine Ausgabe im aktuell angezeigten Datensatz steckt.

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
  fetch_cycling.py           # Wikipedia-Wikitext-Parser (ueberspringt "source": "manual"-Rennen)
  build_manual_cycling.py     # data/manual/stage-race.csv -> data/cycling-<race-id>.json, fuer "source": "manual"-Rennen
  build_ics.py                # data/*.json + config/clubs.json -> public/kalender.ics (unfilterierter Kombi-Feed)
  build_site_data.py          # data/*.json -> public/data/events.json
  tools/
    verify_race_sources.py    # manuell, ~1x/Jahr: scraper-vs-manuell-Entscheidung fuer Kandidatenrennen
    race_candidates.json      # Input-Liste fuer verify_race_sources.py
api/
  calendar.ics.py             # Vercel Python Function: personalisierte /api/calendar.ics
data/                         # ein JSON-Snapshot pro Liga-Quelle (Diff-Basis), z.B. football-bl1.json
  manual/
    stage-race.csv            # manuell gepflegte Etappendaten fuer "source": "manual"-Rennen
public/                       # Vercel Static Root
  index.html / app.js / style.css   # Auswahl-UI (Basis: Claude-Design-Entwurf) + Terminliste
  impressum.html / datenschutz.html # Rechtliches (Platzhalter zum Ausfüllen), im Footer verlinkt
  kalender.ics                # generierte, kombinierte Kalenderdatei (Interims-/Vorschau-Feed)
  data/events.json            # generierte, kombinierte Website-Daten (Terminliste)
  data/clubs.json             # gekürzte Kopie von config/clubs.json fürs Frontend (Auswahl-UI)
  data/leagues.json           # Fußball-Liga-Gruppen fürs Frontend (DFB-Pokal ausgenommen -- kommt automatisch mit)
  data/races.json             # Radsport-Rennen fürs Frontend
vercel.json                   # Vercel-Projektkonfiguration
.github/workflows/update.yml # wöchentlicher Cron + manueller Trigger
```

**Wichtig:** `public/` ist der Vercel Static Root. Nur was dort liegt, ist per HTTP erreichbar – deshalb erzeugt `build_site_data.py` eine kombinierte Kopie unter `public/data/events.json`, obwohl die Roh-Snapshots in `data/` liegen. `data/` und `config/` sind trotzdem Teil des Deployments (nur nicht direkt per URL erreichbar) und genau deshalb kann `api/calendar_ics.py` sie serverseitig lesen.

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

## Impressum & Datenschutz

`public/impressum.html` und `public/datenschutz.html` enthalten **Platzhalter** (`[Platzhalter: ...]`), die vor dem Live-Gang ausgefüllt werden müssen (Name, ladungsfähige Anschrift, E-Mail, zweite Kontaktmöglichkeit) – ohne öffentlichen Zugriffsschutz greift die Ausnahme für "rein private Nutzung" nach § 5 DDG nicht. Beide Seiten sind im Footer jeder Seite verlinkt und verweisen auch gegenseitig aufeinander sowie zurück zur Startseite (max. 2 Klicks von überall).

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

Ein neues Rennen kommt durch einen neuen Eintrag in `config.json` dazu – bei einem scrapebaren Wikipedia-Artikel reicht das allein (`wikipediaTitleTemplate`), sonst zusätzlich `"source": "manual"` plus die Etappendaten in `data/manual/stage-race.csv` (siehe oben und `scripts/build_manual_cycling.py`). Welcher Fall zutrifft, entscheidet `scripts/tools/verify_race_sources.py`. Eine neue Liga (z. B. eine weitere Regionalliga-Staffel) braucht einen neuen Eintrag in `config.json` unter `football.leagues` (mit passendem `scope`: `full`, `club-filter` oder `cup`) plus die entsprechenden Vereine in `config/clubs.json` – kein Umbau von `fetch_football.py` nötig. Ein neuer Verein in einer bereits erfassten Liga kommt automatisch dazu, sobald er bei OpenLigaDB auftaucht; für einen sauber aufgelösten (statt als Klartext angezeigten) Namen braucht er zusätzlich einen Eintrag in `config/clubs.json`. Eine komplett neue Sportart braucht ein neues `fetch_<sportart>.py`, das Events im gleichen Basisschema in `data/<quelle>.json` schreibt, plus einen Fall in `format_event_title()` (`scripts/common.py`); `build_ics.py`, `build_site_data.py` und die Website müssen dafür nicht angefasst werden.

## Vercel einrichten (einmalig)

1. Auf [vercel.com](https://vercel.com) ein neues Projekt aus diesem GitHub-Repo anlegen (eigener Hobby-Plan-Slot, unabhängig von anderen Projekten). Vercel erkennt `api/calendar_ics.py` automatisch als Python Function und `public/` als Static Root (siehe `vercel.json`) – kein Build-Schritt nötig.
2. Damit die Function `data/*.json` + `config/clubs.json` sehen kann, müssen diese Teil des Git-Repos sein (sind sie bereits) – Vercel bündelt beim Deploy alles, was zur Build-Zeit erreichbar ist.
3. Fertig – die Seite liegt danach unter `https://<projekt>.vercel.app/`, der personalisierte Kalenderlink unter `https://<projekt>.vercel.app/api/calendar.ics?t=...` (bzw. `webcal://...`), der unfiltrierte Interims-Feed unter `/kalender.ics`.

Der Workflow `.github/workflows/update.yml` läuft automatisch jeden Montag 06:00 UTC und lässt sich zusätzlich manuell über den Tab „Actions" → „Update sportocal calendar" → „Run workflow" anstoßen. Jeder dadurch entstehende Commit auf dem verbundenen Branch löst automatisch ein Vercel-Redeploy aus (Vercels GitHub-Integration, kein Zutun nötig, sobald das Projekt einmal verbunden ist).

