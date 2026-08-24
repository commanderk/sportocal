# sportocal

Live unter **[sportocal.de](https://sportocal.de)**.

Ein Sport-Kalender (Fußball + Radsport) mit personalisierbarem `.ics`-Abo und einer kleinen Website – gehostet auf Vercel (Hobby-Plan): eine statische Seite unter `public/` und eine Python-Serverless-Function (`api/calendar_ics.py`) für den personalisierten Kalenderlink, aus demselben Repo und Deploy. Die Datenaktualisierung läuft weiterhin wöchentlich im Hintergrund über GitHub Actions (`scripts/fetch_*.py`); jeder daraus entstehende Commit löst automatisch ein Vercel-Redeploy aus, wodurch die Function wieder aktuelle Daten aus dem Deployment-Bundle liest. Kein Login, kein Cookie, kein Server im klassischen Sinn, kein API-Key.

Das Frontend (`public/index.html`/`app.js`, Basis: ein Claude-Design-Entwurf) lässt Nutzer Fußballvereine (gruppiert nach Liga) und Radsport-Rennen per Multi-Select auswählen; ausgewählte Elemente erscheinen als farbige, entfernbare Chips in der jeweiligen Vereinsfarbe. Ohne Auswahl zeigt die Seite eine ungefilterte Vorschau aller Termine; sobald mindestens ein Verein oder Rennen ausgewählt ist, schaltet sich die Abo-Leiste frei: ein `webcal://`-Button ("Kalender abonnieren") plus die reine `https://`-URL zum Kopieren (für Google Calendar, das `webcal://` nicht zuverlässig unterstützt) und eine Klartext-Bestätigungszeile ("Dein Kalender enthält: ..."). Kein Download-Button -- eine heruntergeladene Datei würde sich nie aktualisieren.

## Was drin ist

**Fußball**, alle Vereine aus:
- 1. Bundesliga, 2. Bundesliga, 3. Liga (Herren) – Quelle: [OpenLigaDB](https://api.openligadb.de)
- Frauen-Bundesliga (Quelle: OpenLigaDB), 2. Frauen-Bundesliga (Quelle: DFB Datencenter, siehe unten)
- Regionalliga Südwest, alle 18 Vereine (Quelle: DFB Datencenter, siehe unten)
- DFB-Pokal (Herren) für alle oben genannten Vereine, die daran teilnehmen
- UEFA Champions League, UEFA Europa League, UEFA Conference League – jeweils nur für teilnehmende Vereine aus den obigen Ligen (dieselbe `homeTeamId`/`awayTeamId`-Auflösung wie beim DFB-Pokal, kein eigener Vereinskader nötig)

**DFB-Pokal der Frauen** und **UEFA Conference League**: aktuell (Stand 2026) führt OpenLigaDB dafür keine eigene, befüllte Liga (`dfb-pokal-women` bzw. `uecl`) – beide Quellen sind trotzdem in `config.json` konfiguriert und werden bei jedem Lauf versucht; liefern sie weiterhin nichts, wird das nur geloggt, nicht als Fehler behandelt. Taucht eine Liga dort später auf, greift sie ohne Codeänderung.

**2. Frauen-Bundesliga und Regionalliga Südwest – DFB Datencenter statt OpenLigaDB:** OpenLigaDB liefert für beide Ligen keine verlässlichen aktuellen Daten mehr (2. Frauen-Bundesliga: leer/veraltet; Regionalliga Südwest: letzter Datensatz Saison 2016/17). Beide sind deshalb komplett auf das offizielle [DFB Datencenter](https://datencenter.dfb.de) umgestellt (`primarySource` in `config.json`) – kein Fallback-bei-Miss wie früher bei Regionalliga Südwest, OpenLigaDB wird für diese beiden Ligen gar nicht mehr angefragt (`getavailableleagues`-Ausfälle bei OpenLigaDB betreffen sie entsprechend auch nicht, siehe `make_leagues_getter()` in `fetch_football.py`). Regionalliga Südwest trackte anfangs nur die Stuttgarter Kickers, wurde aber im selben Umbau auf die volle Liga (18 Vereine) ausgebaut: dieselbe Saison-Übersichtsseite ohnehin schon für den Kickers-Umstieg abgerufen wurde, und `parse_dfb_datencenter_page()` beide Seitenformen (Saison-Übersicht wie bei der 2. Frauen-Bundesliga, Team-Einzelseite wie zuvor bei den Kickers) unverändert liest. Kein Spielort pro Match auf diesen Seiten – ein statisches Mapping (`config/stadiums.json`) füllt `location`, wo die Spielstätte recherchiert und bestätigt ist; unvollständig ist hier bewusst besser als geraten.

**Radsport** (Quelle: Wikipedia-Scraper oder manuelle CSV-Pflege, siehe Begründung unten) – 56 Rennen in `config.json` (Stand 2026-08-02):
- Tour de France, Giro d'Italia, Vuelta a España – Wikipedia-gescrapt, alle Einzeletappen (Kernumfang)
- 18 weitere Etappenrennen als `"source": "manual"`-Einträge über `data/manual/stage-race.csv`: Deutschland Tour, Männer-UCI-WorldTour-Rundfahrten (Tour de Pologne, Tour de Suisse, Paris–Nice, Tirreno–Adriatico, …) sowie die Frauen-Grand-Tours und -UCI-WorldTour-Rundfahrten (Tour de France Femmes, Giro d'Italia Women, Vuelta España Femenina, Vuelta a Burgos Feminas, Tour de Suisse Women, …) – ursprünglich als Kandidatenliste in `scripts/tools/race_candidates.json` verifiziert (siehe unten)
- 35 Eintagesrennen als `"source": "manual"`-Einträge über `data/manual/one-day.csv`: die klassischen Monumente (Milano-Sanremo, Ronde van Vlaanderen, Paris-Roubaix, Liège–Bastogne–Liège, Il Lombardia), weitere Männer- und die fast durchgängig gespiegelten Frauen-UCI-WorldTour-Klassiker (Omloop Het Nieuwsblad, Strade Bianche, Flandern-Rundfahrt-Woche, Amstel Gold Race, La Flèche Wallonne, …), plus ADAC Cyclassics Hamburg, Sparkassen Münsterland Giro und zwei weitere deutsche Regionalrennen (Tour de Neuss, Schmitter-Nacht von Hürth)

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

**Die ursprünglich 17 als "Manuell" verifizierten Etappenrennen** (9 Männer-UCI-WorldTour-Etappenrennen + 3 Frauen-Grand-Tour-Kandidaten + 5 weitere Frauen-UCI-WorldTour-Etappenrennen – die komplette Liste aus `scripts/tools/race_candidates.json`) liefen zuerst über dieselbe CSV-Pipeline, die für die deutschen Regional-/ProSeries-Rennen vorgesehen war; inzwischen sind auf demselben Weg weitere Etappenrennen sowie sämtliche Eintagesrennen dazugekommen (56 Config-Einträge insgesamt, siehe "Was drin ist" oben). Ein Eintrag in `config.json` mit `"source": "manual"` (kein `wikipediaTitleTemplate`) sagt `fetch_cycling.py`, dieses Rennen zu überspringen; `scripts/build_manual_cycling.py` liest stattdessen die passende CSV und schreibt denselben additiven Snapshot (`merge_events()`, siehe oben) unter `data/cycling-<race-id>.json` – für `build_ics.py`/`build_site_data.py` nicht unterscheidbar von einem gescrapten Rennen.

Zwei getrennte CSV-Dateien, je nach Renntyp:
- **`data/manual/stage-race.csv`** (Etappenrennen, eine Zeile pro Etappe): Spalten `race_id,year,stage_label,date,start,finish,type,start_time`. `date` als `YYYY-MM-DD`, `type` muss einer der Werte aus `common.STAGE_TYPES` sein. `start_time` ist optional (`HH:MM`, Europe/Berlin) – ist er gesetzt, bekommt die Etappe eine echte, DST-bewusst nach UTC konvertierte Startzeit und `timeConfirmed: true` statt des ganztägigen Platzhalters (siehe `build_stage_events()` in `fetch_cycling.py`, das auch der Wikipedia-Scraper nutzt).
- **`data/manual/one-day.csv`** (Eintagesrennen, eine Zeile pro Austragung): Spalten `race_id,year,date,start,finish,type` – `start`/`finish` dürfen leer bleiben, solange sie noch nicht feststehen.

Eine fehlerhafte Zeile (unbekannter `type`, fehlendes Pflichtfeld, kaputtes Datum) wird nur geloggt und übersprungen, nicht zum Absturz des ganzen Laufs gebracht – **Vorsicht:** das gilt auch für einen Platzhalterwert wie `"TBD"` in `type`, der nicht in `common.STAGE_TYPES` steht. Eine betroffene Etappe fehlt dann komplett im Kalender (nicht nur ohne Uhrzeit), bis der echte Wert nachgetragen wird – ein wiederkehrender Stolperstein, der schon mehrfach unbemerkt ganze Rennen leer gelassen hat. Auch dieses Skript ist **nicht** Teil von `update.yml` – Aufruf bei Bedarf: `python scripts/build_manual_cycling.py`, nachdem eine CSV-Datei gepflegt wurde.

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

**Additiver Merge (nur Radsport):** `fetch_cycling.py` hat keine solche Saison-Kopplung – ein Rennen wird über seine eigene `race_id` abgerufen, unabhängig von einer Liga-Zuordnung. Ein neuer Lauf **ersetzt** den Snapshot deshalb nicht, sondern merged additiv (`merge_events()`): neue Renn-IDs kommen dazu, bestehende IDs werden aktualisiert, aber keine alte ID wird je entfernt, nur weil sie in diesem Lauf nicht erneut geliefert wurde. Vergangene Ausgaben bleiben dadurch dauerhaft in ICS-Datei und Website erhalten, statt beim nächsten Lauf zu verschwinden. Das Datenvolumen bleibt dabei überschaubar (56 Config-Einträge, siehe "Was drin ist" oben, jeweils nur eine Handvoll Termine pro Rennen und Jahr), daher gibt es dafür bewusst kein Zeitfenster-Limit in Web-Ansicht oder ICS. Da dadurch mehrere Ausgaben desselben Eintagesrennens gleichzeitig sichtbar sein können, hängt `eventDisplayTitle()` in `public/app.js` in diesem Fall die Jahreszahl an den Zeilentitel an (z. B. "Cyclassics Hamburg 2026"), sobald mehr als eine Ausgabe im aktuell angezeigten Datensatz steckt.

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
  build_manual_cycling.py     # data/manual/{stage-race,one-day}.csv -> data/cycling-<race-id>.json, fuer "source": "manual"-Rennen
  build_ics.py                # data/*.json + config/clubs.json -> public/kalender.ics (unfilterierter Kombi-Feed)
  build_site_data.py          # data/*.json -> public/data/events.json
  tools/
    verify_race_sources.py    # manuell, ~1x/Jahr: scraper-vs-manuell-Entscheidung fuer Kandidatenrennen
    race_candidates.json      # Input-Liste fuer verify_race_sources.py
api/
  calendar_ics.py             # Vercel Python Function (WSGI-App `app`): personalisierte /api/calendar.ics
data/                         # ein JSON-Snapshot pro Liga-/Renn-Quelle (Diff-Basis), z.B. football-bl1.json
  manual/
    stage-race.csv            # manuell gepflegte Etappendaten fuer "source": "manual"-Etappenrennen
    one-day.csv                # manuell gepflegte Termine fuer "source": "manual"-Eintagesrennen
public/                       # Vercel Static Root
  index.html / app.js / style.css   # Auswahl-UI (Basis: Claude-Design-Entwurf) + Terminliste
  impressum.html / datenschutz.html # Rechtliches (ausgefuellt, siehe unten), im Footer verlinkt
  kalender.ics                # generierte, kombinierte Kalenderdatei (Interims-/Vorschau-Feed)
  data/events.json            # generierte, kombinierte Website-Daten (Terminliste)
  data/clubs.json             # gekürzte Kopie von config/clubs.json fürs Frontend (Auswahl-UI)
  data/leagues.json           # Fußball-Liga-Gruppen fürs Frontend (DFB-Pokal/UEFA-Wettbewerbe ausgenommen -- kommen automatisch mit)
  data/races.json             # Radsport-Rennen fürs Frontend
tests/                        # pytest-Suite fuer scripts/ + api/ (siehe "Tests ausführen")
tests-e2e/                    # Playwright-Suite fuer public/app.js (siehe "Tests ausführen")
vercel.json                   # Vercel-Projektkonfiguration (Static Root, Function-Routing)
pyproject.toml / uv.lock      # Python-Projektmetadaten, u.a. fuer Vercels `uv lock`-Build; requirements*.txt bleiben die Quelle fuer pip/CI
package.json / playwright.config.js # Node-Tooling ausschliesslich fuer die Playwright-Suite (kein Frontend-Build)
.github/workflows/update.yml # wöchentlicher Cron + manueller Trigger
```

**Wichtig:** `public/` ist der Vercel Static Root. Nur was dort liegt, ist per HTTP erreichbar – deshalb erzeugt `build_site_data.py` eine kombinierte Kopie unter `public/data/events.json`, obwohl die Roh-Snapshots in `data/` liegen. `data/` und `config/` sind trotzdem Teil des Deployments (nur nicht direkt per URL erreichbar) und genau deshalb kann `api/calendar_ics.py` sie serverseitig lesen.

## Personalisierter Kalenderlink (`/api/calendar.ics`)

Zustandslos: die Auswahl steckt komplett in der URL, kein serverseitiger Speicher, kein Cookie. Erreichbar sowohl unter `https://sportocal.de/api/calendar.ics` als auch (Vercel-Rewrite, siehe `vercel.json`) direkt unter der Function-Route.

```
GET /api/calendar.ics?t=<selection>
```

`t` ist eine kommagetrennte Liste von Tokens, jedes eines von:

- `<clubId>:men` / `<clubId>:women` – Club-ID aus `config/clubs.json` + Geschlecht, z. B. `fc-bayern-muenchen:men`
- `league:<leagueId>:<gender>` – eine ganze Liga ("Alle Vereine der Bundesliga auswählen" im Picker), z. B. `league:bl1:men`. `<leagueId>` kommt aus `config.json`s `football.leagues` (dieselben IDs, die `public/data/leagues.json` als `league.id` exponiert); wird bei jedem Request frisch gegen `config/clubs.json` aufgelöst, sodass Auf-/Abstieg ein bereits abonniertes Kalender automatisch aktualisiert.
- `raceGroup:<key>` – eine ganze Tier×Gender-Rennguppe (Radsport wird nicht pro Rennen, sondern gruppenweise abonniert), z. B. `raceGroup:uci-worldtour-men`. `<key>` ist `"{tier}-{gender}"` (siehe `common.race_group_key()`); wird ebenfalls bei jedem Request frisch aufgelöst, ein später zur Gruppe hinzugefügtes Rennen erscheint automatisch.

  (Ein früheres `race:<raceId>`-Einzelrennen-Token wurde durch `raceGroup:` ersetzt und wird nicht mehr akzeptiert.)

Beispiel: `?t=fc-bayern-muenchen:men,league:bl1:women,raceGroup:grand-tour-men`

Die Function liest `data/*.json` + `config/clubs.json` aus dem Deployment-Bundle, filtert und generiert die ICS-Datei bei jedem Aufruf neu (kein Caching, `Cache-Control: no-store`) – automatische Kalender-Refreshes bekommen dadurch immer den Stand des letzten wöchentlichen Redeploys. Im generierten Titel bekommt nur ein ausgewählter Verein sein Farb-/Form-Emoji; der Gegner erscheint auch dann als Klartext, wenn er selbst ein bekannter Verein ist (Ausnahme: spielen zwei ausgewählte Vereine gegeneinander, bekommen beide ihr Emoji) – eine über `league:` mitgezogene Vereinsauswahl bekommt bewusst nie ein Emoji, nur individuell ausgewählte Vereine. Unbekannte oder nicht mehr existierende IDs im Parameter werden stillschweigend ignoriert (führt zu einem entsprechend kleineren, aber gültigen Kalender) statt eines Fehlers – ein alter, bereits abonnierter Link soll nie hart brechen. Fehlt der Parameter `t` komplett oder ist leer, antwortet die Function mit `400`.

Enthalten ist immer die komplette aktuelle Saison (vergangene und zukünftige Termine); der Cut auf eine neue Saison passiert implizit beim wöchentlichen Fetch (siehe Datenmodell oben), nicht in dieser Function.

Der Kalendername (`X-WR-CALNAME`) wird pro Auswahl frisch aus `build_calendar_name()` (`api/calendar_ics.py`) gebaut: "Sportocal – {Items}", jedes Item so kurz wie möglich (Vereins-`shortName`, oder eine ganze Liga-/Renngruppe als ein sprechender Name statt einer Mitgliederliste). Ab 3 Items wird auf die ersten 2 + ", u.a." gekürzt, ab mehr als 6 Items (oder wenn nichts auflösbar ist) greift der Fallback "Sportocal – Mein Kalender".

Jedes generierte `VEVENT` bekommt außerdem: `LOCATION` (Stadion/Ort bzw. Zielort der Etappe, falls bekannt), `URL` (`https://sportocal.de`), sowie einen `VALARM` mit fixem Trigger um 08:00 Uhr Europe/Berlin am Tag des Termins (DST-bewusst, unabhängig davon, ob die eigentliche Startzeit schon feststeht) – siehe `build_vevent()`/`build_valarm()` in `scripts/common.py`, gemeinsam genutzt von diesem Endpoint und dem unfiltrierten `public/kalender.ics`.

## Impressum & Datenschutz

`public/impressum.html` und `public/datenschutz.html` sind ausgefüllt (Name, ladungsfähige Anschrift, E-Mail; die Angaben nach § 5 DDG/§ 18 Abs. 2 MStV sind zusätzlich in `Impressum.md` im Repo-Root als Klartext-Quelle gepflegt) – ohne öffentlichen Zugriffsschutz greift die Ausnahme für "rein private Nutzung" nach § 5 DDG nicht, die Seite ist also live und braucht ein echtes Impressum. Beide Seiten sind im Footer jeder Seite verlinkt und verweisen auch gegenseitig aufeinander sowie zurück zur Startseite (max. 2 Klicks von überall).

## Warum Liga-Shortcuts nicht hartkodiert sind

OpenLigaDB ist ein Community-Projekt. `bl1` (1. Bundesliga) ist stabil, aber Shortcuts für kleinere Ligen wie die Frauen-Bundesliga ändern sich von Saison zu Saison (z.B. `fbl2`, `ffb2`, `bl2f` für dieselbe Liga in unterschiedlichen Jahren) oder werden gar nicht gepflegt. `fetch_football.py` ruft deshalb für alle Ligen ohne `primarySource` immer zuerst `getavailableleagues` ab (lazy, siehe `make_leagues_getter()` – Ligen *mit* `primarySource` wie die 2. Frauen-Bundesliga oder Regionalliga Südwest brauchen diesen Aufruf gar nicht erst) und matcht den aktuellen Shortcut per Fuzzy-Match auf den Liga-Namen (Keyword-Listen in `config.json`, z.B. `["bundesliga", "frauen", "2"]`). Ligen, deren neuester Datensatz älter als ein Jahr ist, werden als "nicht mehr gepflegt" behandelt und übersprungen (mit Log-Hinweis) statt veraltete Daten anzuzeigen.

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

## Tests ausführen

Python (`scripts/`, `api/` – `tests/`, pytest):

```bash
pip install -r requirements-dev.txt
pytest
```

Frontend (`public/app.js` – `tests-e2e/`, Playwright, einzige Node-Abhängigkeit im Repo):

```bash
npm install
npx playwright install chromium   # einmalig, lädt den Browser
npm run test:e2e
```

## Erweitern

Ein neues Rennen kommt durch einen neuen Eintrag in `config.json` dazu – bei einem scrapebaren Wikipedia-Artikel reicht das allein (`wikipediaTitleTemplate`), sonst zusätzlich `"source": "manual"` plus die Termine in `data/manual/stage-race.csv` (Etappenrennen) bzw. `data/manual/one-day.csv` (Eintagesrennen), siehe oben und `scripts/build_manual_cycling.py`. Welcher Fall zutrifft, entscheidet `scripts/tools/verify_race_sources.py`. Eine neue Liga (z. B. eine weitere Regionalliga-Staffel) braucht einen neuen Eintrag in `config.json` unter `football.leagues` (mit passendem `scope`: `full`, `club-filter` oder `cup`) plus die entsprechenden Vereine in `config/clubs.json` – kein Umbau von `fetch_football.py` nötig. `scope: "club-filter"` bedeutet dabei nicht nur eine andere Fetch-Strategie (nur bestimmte Vereine statt der ganzen Liga), sondern wirkt sich auch auf die Auswahl-UI aus: die Liga bekommt im Picker keine "(Alle Vereine)"-Sammeloption und kollabiert auch nie zu einem entsprechenden Chip/Kalendernamen (siehe `consolidateFullyCoveredLeagueGroups()` in `app.js` bzw. `build_calendar_name()` in `api/calendar_ics.py`) – sonst würde eine unvollständig erfasste Liga fälschlich Vollständigkeit suggerieren (so ursprünglich bei Regionalliga Südwest, das nur die Stuttgarter Kickers von ~18 echten Vereinen trackte, bis zum vollen Liga-Ausbau; aktuell nutzt keine Liga `club-filter`, der Mechanismus bleibt aber für einen künftigen Fall dieser Art nutzbar). Ein neuer Verein in einer bereits erfassten Liga kommt automatisch dazu, sobald er bei OpenLigaDB auftaucht; für einen sauber aufgelösten (statt als Klartext angezeigten) Namen braucht er zusätzlich einen Eintrag in `config/clubs.json`. Eine komplett neue Sportart braucht ein neues `fetch_<sportart>.py`, das Events im gleichen Basisschema in `data/<quelle>.json` schreibt, plus einen Fall in `format_event_title()` (`scripts/common.py`); `build_ics.py`, `build_site_data.py` und die Website müssen dafür nicht angefasst werden.

## Vercel einrichten (einmalig)

1. Auf [vercel.com](https://vercel.com) ein neues Projekt aus diesem GitHub-Repo anlegen (eigener Hobby-Plan-Slot, unabhängig von anderen Projekten). Vercel erkennt `api/calendar_ics.py` automatisch als Python Function und `public/` als Static Root (siehe `vercel.json`) – kein Build-Schritt nötig.
2. Damit die Function `data/*.json` + `config/clubs.json` sehen kann, müssen diese Teil des Git-Repos sein (sind sie bereits) – Vercel bündelt beim Deploy alles, was zur Build-Zeit erreichbar ist.
3. Fertig – die Seite liegt danach unter `https://<projekt>.vercel.app/`, der personalisierte Kalenderlink unter `https://<projekt>.vercel.app/api/calendar.ics?t=...` (bzw. `webcal://...`), der unfiltrierte Interims-Feed unter `/kalender.ics`.
4. Optional: eigene Domain in den Vercel-Projekteinstellungen verbinden. Produktiv läuft das Projekt unter der eigenen Domain **sportocal.de** (statt `<projekt>.vercel.app`) – `SPORTOCAL_URL`/`SPORTOCAL_DOMAIN` in `scripts/common.py` sind hart auf `https://sportocal.de` gesetzt (u. a. für die `URL`-Property in jedem generierten `VEVENT`, siehe oben) und müssten bei einer anderen Domain dort angepasst werden.

Der Workflow `.github/workflows/update.yml` läuft automatisch jeden Montag 06:00 UTC und lässt sich zusätzlich manuell über den Tab „Actions" → „Update sportocal calendar" → „Run workflow" anstoßen. Jeder dadurch entstehende Commit auf dem verbundenen Branch löst automatisch ein Vercel-Redeploy aus (Vercels GitHub-Integration, kein Zutun nötig, sobald das Projekt einmal verbunden ist).

