const SPORT_LABELS = {
  football: "⚽ Fußball",
  cycling: "🚴 Radsport",
};
const SPORT_ORDER = ["football", "cycling"];

// Per-row gender cue for cycling (see eventDisplayTitle()) -- several
// men's/women's one-day classics share the exact same competition name
// (e.g. "Ronde Van Brugge"), so without this the row title alone can't
// tell them apart. Same mapping as scripts/common.py's CYCLING_GENDER_EMOJI,
// used there for the ICS calendar title. Falls back to the plain bicycle
// for any event missing gender (shouldn't happen for current data, but see
// that Python-side fallback for why: older snapshots from before this
// field existed).
const CYCLING_GENDER_EMOJI = { men: "🚴‍♂️", women: "🚴‍♀️" };

// Visual grouping color per selectable football league (used for the
// checkbox accent / swatch in the combobox) -- distinct from a club's own
// colorHex, which is used for that club's dot/chip so it stays recognizable
// on its own once it's out of the grouped list.
const LEAGUE_COLORS = {
  bl1: "#d92b1c",
  bl2: "#0f5fd9",
  bl3: "#0a7a6b",
  ffb1: "#c2185b",
  ffb2: "#7b3fa0",
  "rlsw-kickers": "#e8720c",
};

// Currently unreferenced: the cycling picker moved to group-level selection
// (see renderCyclingCombo()), so there are no more per-race rows/chips to
// color. Kept rather than deleted -- these are real logo-derived hex values,
// not estimates, and a future per-race UI (e.g. a color accent on individual
// event rows) would otherwise have to re-source them from scratch.
const RACE_COLORS = {
  "tour-de-france": "#e8b400",
  "giro-d-italia": "#d81b8f",
  "vuelta-a-espana": "#d92b1c",
  "cyclassics-hamburg": "#0f5fd9",
  "muensterland-giro": "#0a7a6b",
  "deutschland-tour": "#141414",

  // 17 Etappenrennen
  "paris-nice": "#1878c4",
  "tirreno-adriatico": "#003D82",
  "volta-ciclista-a-catalunya": "#e2231a",
  "itzulia-basque-country": "#ED6A21",
  "tour-de-romandie": "#D2232A",
  "tour-auvergne-rhone-alpes": "#4a90d9",
  "tour-de-suisse": "#D52B1E",
  "tour-de-pologne": "#DC1428",
  "renewi-tour": "#009688",
  "tour-de-france-femmes": "#f2e100",
  "giro-d-italia-women": "#E61E73",
  "vuelta-espana-femenina": "#d0201a",
  "itzulia-women": "#ED6A21",
  "vuelta-a-burgos-feminas": "#C8102E",
  "tour-de-suisse-women": "#D52B1E",
  "tour-of-britain-women": "#00205B",
  "tour-de-romandie-feminin": "#4B3F72",

  // 14 Eintagesklassiker (Frauen) -- IDs matchen config.json
  "omloop-het-nieuwsblad-women": "#F26522",
  "strade-bianche-donne": "#8C6D46",
  "trofeo-alfredo-binda": "#0057A0",
  "milano-sanremo-women": "#C8102E",
  "ronde-van-brugge-women": "#1A1A1A",
  "in-flanders-fields-women": "#C8102E",
  "dwars-door-vlaanderen-women": "#FFD700",
  "ronde-van-vlaanderen-women": "#FFD700",
  "paris-roubaix-femmes": "#1A1A1A",
  "amstel-gold-race-ladies": "#E2001A",
  "fleche-wallonne-femmes": "#FFD90F",
  "liege-bastogne-liege-femmes": "#6B2C4E",
  "copenhagen-sprint-women": "#C8102E",
  "classic-lorient": "#1B1B3A",
};

// Visual accent per cycling tier×gender group (picker checkbox + chip) --
// same role LEAGUE_COLORS plays for football's group-select-all rows.
// Deliberately not derived from RACE_COLORS: a group mixes many races with
// different colors, so it needs its own single accent. A group key with no
// entry here (e.g. a future "uci-proseries-women") falls back to #141414,
// same fallback RACE_COLORS already uses for unlisted races.
const RACE_GROUP_COLORS = {
  "grand-tour-men": "#e8b400",
  "grand-tour-women": "#d81b8f",
  "uci-worldtour-men": "#2f6fed",
  "uci-worldtour-women": "#a8325e",
  "uci-proseries-men": "#3d8f7a",
  "regional-men": "#c9622a",
};

// Stable, URL-safe key identifying a race's tier×gender group -- same
// derivation as scripts/common.py's race_group_key(), used server-side by
// api/calendar_ics.py to resolve a "raceGroup:<key>" token back to the
// current set of config.json races on every request. Groups already carry
// tier/gender (see build_site_data.py's build_race_groups_payload()), so no
// new races.json field is needed for this.
function raceGroupKey(group) {
  return `${group.tier}-${group.gender}`;
}

const dateFormatter = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit",
  month: "short",
  timeZone: "Europe/Berlin",
});
const timeFormatter = new Intl.DateTimeFormat("de-DE", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Berlin",
});
const weekdayFormatter = new Intl.DateTimeFormat("de-DE", { weekday: "short", timeZone: "Europe/Berlin" });
const dayNumFormatter = new Intl.DateTimeFormat("de-DE", { day: "2-digit", timeZone: "Europe/Berlin" });
const monthNumFormatter = new Intl.DateTimeFormat("de-DE", { month: "2-digit", timeZone: "Europe/Berlin" });

function formatShortDate(d) {
  return `${dayNumFormatter.format(d)}.${monthNumFormatter.format(d)}.`;
}

// Picks readable chip/dot text color for an arbitrary club brand color --
// some clubs (e.g. all-white kits) are too light for the usual off-white text.
function contrastText(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? "#141414" : "#f6f5f2";
}

// The row-index number is the event's actual Spieltag (matchday) or Etappe
// (stage) number, taken from `round` (e.g. "Spieltag 27", "Etappe 18",
// "1. Runde") -- not a sequential per-section counter -- so it always means
// something a viewer recognizes from the competition itself.
function extractRoundNumber(round) {
  const match = /\d+/.exec(round || "");
  return match ? match[0].padStart(2, "0") : "";
}

// Cycling snapshots now merge additively across years (see README), so a
// one-day race's past and future editions can both be in view at once, with
// the same title -- that's ambiguous especially in "Nach Datum", where they
// aren't grouped together the way "Nach Wettbewerb" groups a competition's
// own upcoming/past rows. computeDuplicateOneDayCompetitions() below,
// populated once per render() call, is a deliberate module-level-state
// shortcut so eventDisplayTitle() can see it without threading a parameter
// through renderByDate/renderByCompetition/renderCompetitionSection/renderEventRow.
let duplicateOneDayCompetitions = new Set();

function computeDuplicateOneDayCompetitions(events) {
  const counts = new Map();
  for (const event of events) {
    if (event.sport === "cycling" && !event.round) {
      counts.set(event.competition, (counts.get(event.competition) || 0) + 1);
    }
  }
  return new Set([...counts].filter(([, count]) => count > 1).map(([name]) => name));
}

// The web view's row-title is a stripped-down label, not the full calendar
// title: no emoji, no "Spieltag" round marker for football (already shown as
// the row-index there). Cycling does need its round spelled out here though
// -- unlike football's competition-named section headers ("Bundesliga"),
// "Nach Datum" has no per-row grouping to fall back on, and the section
// header in "Nach Wettbewerb" is the competition name, not the round. Route
// (start → finish) is detail for the venue column (see renderEventRow()),
// never the title -- a bare "Neuss → Neuss" or "Lausanne → Genf" doesn't say
// which race it even is. The full calendar title (with club color/gender
// emoji) is generated separately at ICS build time from these same raw
// fields, not stored on the event.
function eventDisplayTitle(event) {
  if (event.sport === "football") {
    return [event.homeTeamName, event.awayTeamName].filter(Boolean).join(" – ");
  }
  const emoji = CYCLING_GENDER_EMOJI[event.gender] || "🚴";
  if (event.round) {
    return `${emoji} ${event.competition}, ${event.round}`;
  }
  if (duplicateOneDayCompetitions.has(event.competition)) {
    return `${emoji} ${event.competition} ${event.start.slice(0, 4)}`;
  }
  return `${emoji} ${event.competition}`;
}

function parseStart(start) {
  // date-only strings ("2026-07-04") are parsed as UTC midnight by Date(),
  // which is fine here since we only use them for day-granularity comparisons.
  return new Date(start);
}

function isAllDay(start) {
  return start.length === 10;
}

// Single source of truth for "is this event in the past", used for both
// sorting and graying out rows. Comparison is by calendar day in
// Europe/Berlin (not exact instant), so a match that already kicked off
// earlier today still counts as "today", not "past" -- and cycling's
// date-only events compare on equal footing with football's exact times.
const berlinDayFormatter = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Berlin" });

function dayKey(event) {
  return isAllDay(event.start) ? event.start : berlinDayFormatter.format(parseStart(event.start));
}

function isPastEvent(event) {
  return dayKey(event) < berlinDayFormatter.format(new Date());
}

function isToday(event) {
  return dayKey(event) === berlinDayFormatter.format(new Date());
}

function groupBy(items, keyFn) {
  const map = new Map();
  for (const item of items) {
    const key = keyFn(item);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(item);
  }
  return map;
}

function renderEventRow(event) {
  const startDate = parseStart(event.start);
  const row = document.createElement("div");
  row.className = "event-row" +
    (isPastEvent(event) ? " is-past" : "") +
    (isToday(event) ? " is-today" : "");

  const roundNumber = extractRoundNumber(event.round);
  const timeText = event.timeConfirmed && !isAllDay(event.start)
    ? timeFormatter.format(startDate)
    : "tbd";
  const titleText = eventDisplayTitle(event);
  // Route (start → finish) is the venue-column detail for cycling rows now
  // that the title is always the race name (+ round) -- see eventDisplayTitle().
  // Falls back to plain `location` when start/finish aren't both known yet
  // (e.g. a manually-entered race awaiting confirmed dates/venues, route
  // still present but start/finish left blank -- see data/manual/*.csv).
  const venueText = event.route && event.route.start && event.route.finish
    ? `${event.route.start} → ${event.route.finish}`
    : event.location || "";

  const desktop = document.createElement("div");
  desktop.className = "row-desktop";
  row.appendChild(desktop);

  const idx = document.createElement("div");
  idx.className = "row-index";
  idx.textContent = roundNumber;
  desktop.appendChild(idx);

  const dateCol = document.createElement("div");
  dateCol.className = "row-date";
  dateCol.innerHTML = `${weekdayFormatter.format(startDate)}<span class="row-daynum">${formatShortDate(startDate)}</span>`;
  desktop.appendChild(dateCol);

  const timeCol = document.createElement("div");
  timeCol.className = "row-time";
  timeCol.textContent = timeText;
  desktop.appendChild(timeCol);

  const logos = document.createElement("div");
  logos.className = "row-logos";
  if (event.homeTeamLogo) {
    logos.appendChild(Object.assign(document.createElement("img"), { src: event.homeTeamLogo, alt: "", loading: "lazy" }));
  }
  if (event.awayTeamLogo) {
    logos.appendChild(Object.assign(document.createElement("img"), { src: event.awayTeamLogo, alt: "", loading: "lazy" }));
  }
  desktop.appendChild(logos);

  const title = document.createElement("div");
  title.className = "row-title";
  title.textContent = titleText;
  desktop.appendChild(title);

  const venue = document.createElement("div");
  venue.className = "row-venue";
  venue.textContent = venueText;
  desktop.appendChild(venue);

  // Below ~900px .row-desktop is hidden in favor of this compact two-line
  // layout (round index + teams/logos, then weekday/date · time · venue) so
  // mobile keeps the same information instead of just hiding columns.
  const mobile = document.createElement("div");
  mobile.className = "row-mobile";
  row.appendChild(mobile);

  const mobileMain = document.createElement("div");
  mobileMain.className = "row-mobile-main";
  mobile.appendChild(mobileMain);

  const mobileIdx = document.createElement("span");
  mobileIdx.className = "row-mobile-index";
  mobileIdx.textContent = roundNumber;
  mobileMain.appendChild(mobileIdx);

  if (event.sport === "football") {
    const home = document.createElement("span");
    home.className = "row-mobile-team";
    home.textContent = event.homeTeamName || "";
    mobileMain.appendChild(home);
    if (event.homeTeamLogo) {
      mobileMain.appendChild(Object.assign(document.createElement("img"), { src: event.homeTeamLogo, alt: "", loading: "lazy", className: "row-mobile-logo" }));
    }
    const sep = document.createElement("span");
    sep.className = "row-mobile-sep";
    sep.textContent = "–";
    mobileMain.appendChild(sep);
    if (event.awayTeamLogo) {
      mobileMain.appendChild(Object.assign(document.createElement("img"), { src: event.awayTeamLogo, alt: "", loading: "lazy", className: "row-mobile-logo" }));
    }
    const away = document.createElement("span");
    away.className = "row-mobile-team";
    away.textContent = event.awayTeamName || "";
    mobileMain.appendChild(away);
  } else {
    const mobileTitle = document.createElement("span");
    mobileTitle.className = "row-mobile-title";
    mobileTitle.textContent = titleText;
    mobileMain.appendChild(mobileTitle);
  }

  const mobileMeta = document.createElement("div");
  mobileMeta.className = "row-mobile-meta";
  mobileMeta.textContent = [
    `${weekdayFormatter.format(startDate)} ${formatShortDate(startDate)}`,
    timeText,
    venueText,
  ].filter(Boolean).join(" · ");
  mobile.appendChild(mobileMeta);

  return row;
}

function renderCompetitionSection(competitionName, events) {
  const section = document.createElement("div");
  section.className = "competition-group";

  const header = document.createElement("div");
  header.className = "competition-header";
  const h3 = document.createElement("h3");
  h3.textContent = competitionName;
  header.appendChild(h3);

  const upcoming = events.filter((e) => !isPastEvent(e)).sort((a, b) => a.start.localeCompare(b.start));
  const past = events.filter((e) => isPastEvent(e)).sort((a, b) => b.start.localeCompare(a.start));

  const count = document.createElement("span");
  count.className = "competition-count";
  count.textContent = `${events.length} Termin${events.length === 1 ? "" : "e"}`;
  header.appendChild(count);
  section.appendChild(header);

  if (upcoming.length === 0 && past.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Keine Termine bekannt.";
    section.appendChild(empty);
    return section;
  }

  // Every section applies the exact same rule: upcoming first (bright), then
  // a labelled divider, then past events (grayed) -- so it's always visible
  // *why* a row is grayed, whether a section has one past match or a whole
  // finished season.
  for (const event of upcoming) {
    section.appendChild(renderEventRow(event));
  }
  if (past.length > 0) {
    const divider = document.createElement("p");
    divider.className = "past-divider";
    divider.textContent =
      upcoming.length > 0
        ? "Vergangene Termine"
        : "Vergangene Termine (noch keine kommenden Termine bekannt)";
    section.appendChild(divider);
    for (const event of past) {
      section.appendChild(renderEventRow(event));
    }
  }

  return section;
}

function renderByDate(events, app) {
  // One continuous chronological list across every sport/competition, using
  // the exact same upcoming-then-past-with-divider rule as the grouped view.
  const upcoming = events.filter((e) => !isPastEvent(e)).sort((a, b) => a.start.localeCompare(b.start));
  const past = events.filter((e) => isPastEvent(e)).sort((a, b) => b.start.localeCompare(a.start));

  const section = document.createElement("section");
  section.className = "sport-section";
  for (const event of upcoming) {
    section.appendChild(renderEventRow(event));
  }
  if (past.length > 0) {
    const divider = document.createElement("p");
    divider.className = "past-divider";
    divider.textContent = "Vergangene Termine";
    section.appendChild(divider);
    for (const event of past) {
      section.appendChild(renderEventRow(event));
    }
  }
  app.appendChild(section);
}

// A filter pill's value is either a plain league name (football, matches
// event.competition directly) or "raceGroup:<key>" (cycling, one pill covers
// every race in that tier×gender group -- see getFilterItemsInOrder()). A
// single competitionName here is always one race/league, never a group, so
// resolving a raceGroup: filter back to "does this race belong to it" goes
// through state.races the same way visibleEvents() already does.
function competitionMatchesFilter(competitionName, filter) {
  if (filter === FILTER_ALL) return true;
  if (filter.startsWith("raceGroup:")) {
    const key = filter.slice("raceGroup:".length);
    const race = state.races.find((r) => r.name === competitionName);
    return Boolean(race && race.groupKey === key);
  }
  return competitionName === filter;
}

function renderByCompetition(events, app, competitionFilter) {
  const bySport = groupBy(events, (e) => e.sport);
  const sportKeys = [...bySport.keys()].sort(
    (a, b) => SPORT_ORDER.indexOf(a) - SPORT_ORDER.indexOf(b)
  );

  for (const sport of sportKeys) {
    const sportEvents = bySport.get(sport);
    const byCompetition = groupBy(sportEvents, (e) => e.competition);
    // Competitions with upcoming fixtures are sorted to the top by their next
    // date; competitions with nothing upcoming (e.g. a season whose next
    // fixtures aren't published yet) sink to the bottom instead of jumping
    // to the front just because their old dates happen to be numerically small.
    const sortKey = (evts) => {
      const future = evts.filter((e) => !isPastEvent(e));
      if (future.length) {
        return [0, Math.min(...future.map((e) => parseStart(e.start).getTime()))];
      }
      return [1, -Math.max(...evts.map((e) => parseStart(e.start).getTime()))];
    };
    const competitionNames = [...byCompetition.keys()].sort((a, b) => {
      const [aTier, aValue] = sortKey(byCompetition.get(a));
      const [bTier, bValue] = sortKey(byCompetition.get(b));
      return aTier !== bTier ? aTier - bTier : aValue - bValue;
    });

    // A selected cycling filter pill covers a whole tier×gender group, so
    // every race belonging to it still gets its own renderCompetitionSection()
    // below -- only the filter *pills* are grouped, not the results list.
    const visibleNames = competitionNames.filter((name) => competitionMatchesFilter(name, competitionFilter));
    if (visibleNames.length === 0) continue;

    const sportSection = document.createElement("section");
    sportSection.className = "sport-section";
    const h2 = document.createElement("h2");
    h2.textContent = SPORT_LABELS[sport] || sport;
    sportSection.appendChild(h2);

    for (const competitionName of visibleNames) {
      sportSection.appendChild(renderCompetitionSection(competitionName, byCompetition.get(competitionName)));
    }
    app.appendChild(sportSection);
  }
}

const FILTER_ALL = "Alle";

// Filter pills mostly mirror the two multiselects' *selection state* --
// league pills come from state.leagues (a club statically belongs to its
// league regardless of whether it currently has a fixture in view) and
// cycling group pills from state.raceGroups, same grouping their comboboxes
// already use. Cup/UEFA competitions (DFB-Pokal, Champions League, Europa
// League, ...) have no such static per-club membership -- a club doesn't
// "belong" to a cup the way it belongs to a league, it just happens to have
// a fixture there this season -- so those pills instead mirror the actual
// competition names present in visibleEvents(), same as the old pre-grouping
// behavior, just restricted to whichever football competitions aren't
// already covered by a league pill.
function getFilterItemsInOrder() {
  const items = [];
  const leagueNames = new Set(state.leagues.map((l) => l.competition));
  const footballEvents = visibleEvents().filter((e) => e.sport === "football");

  if (!hasSelection()) {
    for (const league of state.leagues) {
      items.push({ value: league.competition, label: league.competition });
    }
  } else {
    // club.teams[gender].league (see clubs.json) is the same league name used
    // as event.competition for that club's matches -- collecting distinct
    // values here, then walking state.leagues to pick the pill order, keeps
    // pills in league order without re-sorting alphabetically.
    const selectedLeagueNames = new Set();
    for (const token of state.selectedClubs) {
      const [clubId, gender] = token.split(":");
      const club = state.clubsById.get(clubId);
      const teamInfo = club && club.teams[gender];
      if (teamInfo) selectedLeagueNames.add(teamInfo.league);
    }
    for (const league of state.leagues) {
      if (selectedLeagueNames.has(league.competition)) {
        items.push({ value: league.competition, label: league.competition });
      }
    }
  }

  const extraCompetitionNames = [...new Set(footballEvents.map((e) => e.competition))]
    .filter((name) => !leagueNames.has(name))
    .sort((a, b) => a.localeCompare(b, "de"));
  for (const name of extraCompetitionNames) {
    items.push({ value: name, label: name });
  }

  if (!hasSelection()) {
    for (const group of state.raceGroups) {
      items.push({ value: `raceGroup:${raceGroupKey(group)}`, label: group.label });
    }
  } else {
    for (const group of state.raceGroups) {
      const key = raceGroupKey(group);
      if (state.selectedRaceGroups.has(key)) {
        items.push({ value: `raceGroup:${key}`, label: group.label });
      }
    }
  }

  return items;
}

function renderCompetitionFilters() {
  const container = document.getElementById("competition-filters");
  container.innerHTML = "";
  const items = [{ value: FILTER_ALL, label: FILTER_ALL }, ...getFilterItemsInOrder()];
  if (!items.some((item) => item.value === state.competitionFilter)) state.competitionFilter = FILTER_ALL;
  for (const item of items) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "filter-pill" + (state.competitionFilter === item.value ? " is-active" : "");
    btn.textContent = item.label;
    btn.addEventListener("click", () => {
      state.competitionFilter = item.value;
      renderCompetitionFilters();
      render();
    });
    container.appendChild(btn);
  }
}

// Rough client detection to pick a sensible default calendar-app tab -- not
// exhaustive, just nice-to-have so most visitors don't have to switch tabs
// at all. Anyone not matched falls back to "apple", the most direct path.
function detectDefaultApp() {
  const ua = navigator.userAgent || "";
  if (/Android/.test(ua)) return "google";
  if (/Windows/.test(ua)) return "outlook";
  return "apple";
}

const state = {
  events: [],
  clubs: [],
  clubsById: new Map(),
  leagues: [],
  raceGroups: [], // server-grouped (tier, gender-suffixed where needed) races, see build_site_data.py
  races: [], // flattened from raceGroups, each augmented with tier/gender/groupKey -- for id/name lookups
  viewMode: "competition",
  competitionFilter: FILTER_ALL,
  selectedClubs: new Set(), // tokens "<clubId>:<gender>"
  selectedRaceGroups: new Set(), // tier×gender group keys, see raceGroupKey() -- cycling selection is group-level, not per-race
  footballOpen: false,
  cyclingOpen: false,
  search: "", // football combobox search (kept separate from cyclingSearch so the two panels don't filter each other)
  cyclingSearch: "",
  activeApp: detectDefaultApp(),
  fallbackOpen: false,
  stickyVisible: false,
};

// --- selection-aware event list ----------------------------------------

function hasSelection() {
  return state.selectedClubs.size > 0 || state.selectedRaceGroups.size > 0;
}

// Without a selection the list is an unfiltered preview of everything, same
// spirit as the design mock -- so the page is never empty on first load.
function visibleEvents() {
  if (!hasSelection()) return state.events;
  return state.events.filter((e) => {
    if (e.sport === "football") {
      return (
        (state.selectedClubs.has(`${e.homeTeamId}:${e.gender}`) ||
          state.selectedClubs.has(`${e.awayTeamId}:${e.gender}`))
      );
    }
    if (e.sport === "cycling") {
      const race = state.races.find((r) => r.name === e.competition);
      return race && state.selectedRaceGroups.has(race.groupKey);
    }
    return false;
  });
}

function render() {
  const app = document.getElementById("app");
  app.innerHTML = "";

  const events = visibleEvents();
  duplicateOneDayCompetitions = computeDuplicateOneDayCompetitions(events);
  document.getElementById("count-label").textContent = hasSelection()
    ? `${events.length} Termine für deine Auswahl`
    : `${events.length} Termine · Vorschau`;

  if (events.length === 0) {
    app.innerHTML = '<p class="empty-state">Für diese Auswahl liegen aktuell keine Termine vor.</p>';
    return;
  }

  if (state.viewMode === "date") {
    renderByDate(events, app);
  } else {
    renderByCompetition(events, app, state.competitionFilter);
  }
}

// --- selection UI: football combobox ------------------------------------

function clubMatchesSearch(club) {
  if (!state.search.trim()) return true;
  return club.name.toLowerCase().includes(state.search.trim().toLowerCase());
}

function renderFootballCombo() {
  const body = document.getElementById("football-combo-body");
  body.innerHTML = "";

  for (const league of state.leagues) {
    const clubs = state.clubs
      .filter((c) => c.teams[league.gender] && c.teams[league.gender].league === league.competition)
      .filter(clubMatchesSearch)
      .sort((a, b) => a.name.localeCompare(b.name, "de"));
    if (clubs.length === 0) continue;

    const color = LEAGUE_COLORS[league.id] || "#141414";
    const tokens = clubs.map((c) => `${c.id}:${league.gender}`);
    const selectedCount = tokens.filter((t) => state.selectedClubs.has(t)).length;
    const allSelected = selectedCount === tokens.length;
    const someSelected = selectedCount > 0 && !allSelected;

    const head = document.createElement("div");
    head.className = "league-group-head sticky-group-header";
    const label = document.createElement("label");
    label.className = "league-group-label";
    const allCheckbox = document.createElement("input");
    allCheckbox.type = "checkbox";
    allCheckbox.checked = allSelected;
    allCheckbox.indeterminate = someSelected;
    allCheckbox.style.accentColor = color;
    allCheckbox.addEventListener("change", () => {
      if (allSelected) tokens.forEach((t) => state.selectedClubs.delete(t));
      else tokens.forEach((t) => state.selectedClubs.add(t));
      refreshSelectionUI();
    });
    const swatch = document.createElement("span");
    swatch.className = "league-swatch";
    swatch.style.background = color;
    const name = document.createElement("span");
    name.className = "league-group-name";
    name.textContent = `Alle Vereine der ${league.competition} auswählen`;
    const count = document.createElement("span");
    count.className = "league-group-count";
    count.textContent = `(${tokens.length})`;
    label.append(allCheckbox, swatch, name, count);
    head.appendChild(label);
    body.appendChild(head);

    for (const club of clubs) {
      const token = `${club.id}:${league.gender}`;
      const row = document.createElement("label");
      row.className = "club-row";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = state.selectedClubs.has(token);
      checkbox.addEventListener("change", () => {
        if (state.selectedClubs.has(token)) state.selectedClubs.delete(token);
        else state.selectedClubs.add(token);
        refreshSelectionUI();
      });
      const dot = document.createElement("span");
      dot.className = "club-dot";
      dot.style.background = club.colorHex;
      const clubName = document.createElement("span");
      clubName.textContent = club.name;
      row.append(checkbox, dot, clubName);
      body.appendChild(row);
    }
  }
}

function renderFootballChips() {
  const container = document.getElementById("football-chips");
  container.innerHTML = "";
  for (const token of state.selectedClubs) {
    const [clubId] = token.split(":");
    const club = state.clubsById.get(clubId);
    if (!club) continue;
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.style.background = club.colorHex;
    chip.style.color = contrastText(club.colorHex);
    const name = document.createElement("span");
    name.textContent = club.name;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "✕";
    remove.addEventListener("click", () => {
      state.selectedClubs.delete(token);
      refreshSelectionUI();
    });
    chip.append(name, remove);
    container.appendChild(chip);
  }
  document.getElementById("football-empty-hint").hidden = state.selectedClubs.size > 0;
}

// --- selection UI: cycling combobox -------------------------------------

function raceGroupMatchesSearch(group) {
  if (!state.cyclingSearch.trim()) return true;
  return group.label.toLowerCase().includes(state.cyclingSearch.trim().toLowerCase());
}

// Cycling is selected at the tier×gender group level, not per-race (see
// commit history): with 56+ races and growing, a 56-chip row was unusable,
// and group-level selection makes a subscribed calendar automatically pick
// up new races added to an already-selected group later (resolved fresh on
// every ICS request server-side, see api/calendar_ics.py). So each group
// gets exactly one checkbox here -- no nested per-race rows, no
// all-selected/indeterminate tri-state, groups are atomic (all or nothing).
// Groups themselves (tier, gender-suffixed where a tier has both genders)
// come pre-computed from races.json (build_race_groups_payload() in
// build_site_data.py).
function renderCyclingCombo() {
  const body = document.getElementById("cycling-combo-body");
  body.innerHTML = "";

  for (const group of state.raceGroups) {
    if (!raceGroupMatchesSearch(group)) continue;

    const key = raceGroupKey(group);
    const color = RACE_GROUP_COLORS[key] || "#141414";

    const head = document.createElement("div");
    head.className = "league-group-head";
    const label = document.createElement("label");
    label.className = "league-group-label";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selectedRaceGroups.has(key);
    checkbox.style.accentColor = color;
    checkbox.addEventListener("change", () => {
      if (state.selectedRaceGroups.has(key)) state.selectedRaceGroups.delete(key);
      else state.selectedRaceGroups.add(key);
      refreshSelectionUI();
    });
    const swatch = document.createElement("span");
    swatch.className = "league-swatch";
    swatch.style.background = color;
    const name = document.createElement("span");
    name.className = "league-group-name";
    name.textContent = group.label;
    const count = document.createElement("span");
    count.className = "league-group-count";
    count.textContent = `(${group.races.length} Rennen)`;
    label.append(checkbox, swatch, name, count);
    head.appendChild(label);
    body.appendChild(head);
  }
}

function renderCyclingChips() {
  const container = document.getElementById("cycling-chips");
  container.innerHTML = "";
  for (const key of state.selectedRaceGroups) {
    const group = state.raceGroups.find((g) => raceGroupKey(g) === key);
    if (!group) continue;
    const color = RACE_GROUP_COLORS[key] || "#141414";
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.style.background = color;
    chip.style.color = contrastText(color);
    const name = document.createElement("span");
    name.textContent = group.label;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "✕";
    remove.addEventListener("click", () => {
      state.selectedRaceGroups.delete(key);
      refreshSelectionUI();
    });
    chip.append(name, remove);
    container.appendChild(chip);
  }
  document.getElementById("cycling-empty-hint").hidden = state.selectedRaceGroups.size > 0;
}

// --- subscribe bar --------------------------------------------------------

function buildSelectionToken() {
  const clubTokens = [...state.selectedClubs];
  const raceGroupTokens = [...state.selectedRaceGroups].map((key) => `raceGroup:${key}`);
  return [...clubTokens, ...raceGroupTokens].join(",");
}

function selectionSummaryText() {
  const clubNames = [...state.selectedClubs]
    .map((t) => state.clubsById.get(t.split(":")[0]))
    .filter(Boolean)
    .map((c) => c.name);
  const raceGroupNames = [...state.selectedRaceGroups]
    .map((key) => state.raceGroups.find((g) => raceGroupKey(g) === key))
    .filter(Boolean)
    .map((g) => g.label);
  return [...clubNames, ...raceGroupNames].join(", ");
}

// --- subscribe app tabs (Apple/Outlook/Google/Andere) --------------------

// Apple and Outlook both support subscribing straight off a webcal:// link,
// so they get a primary CTA button with the raw URL tucked behind a
// collapsed "doesn't work?" fallback. Google's webcal:// support is
// unreliable, so instead of a button that silently fails it goes straight
// to numbered steps plus an always-visible URL to paste -- same visible
// pattern as "Andere", which has no app-specific steps of its own.
const SUBSCRIBE_APPS = [
  {
    id: "apple",
    label: "Apple Kalender",
    direct: true,
    ctaLabel: "Für Apple Kalender hinzufügen",
    caption: "Öffnet automatisch deine Kalender-App und fragt nach Bestätigung.",
    fallbackHint: "Falls sich nichts öffnet: Kopiere den Link und füge ihn unter Einstellungen → Kalender → Accounts → Account hinzufügen → Andere → Kalenderabo hinzufügen ein.",
  },
  {
    id: "outlook",
    label: "Outlook",
    direct: true,
    ctaLabel: "Für Outlook hinzufügen",
    caption: "Öffnet Outlook und schlägt vor, den Kalender zu abonnieren.",
    fallbackHint: "Falls sich nichts öffnet: Kopiere den Link und füge ihn unter Kalender → Kalender hinzufügen → Aus dem Internet ein.",
  },
  {
    id: "google",
    label: "Google Kalender",
    direct: false,
    steps: [
      "Öffne Google Kalender am Computer.",
      "Klicke neben „Weitere Kalender“ auf + → „Per URL“.",
      "Füge den Link unten ein und bestätige mit „Kalender hinzufügen“.",
    ],
    pasteHint: "Hier einfügen bei „Per URL hinzufügen“:",
  },
  {
    id: "other",
    label: "Andere",
    direct: false,
    simpleNote: "Kopiere diesen Link und füge ihn in den Kalender-Einstellungen deiner App hinzu (meist unter „Kalender abonnieren“ oder „Von URL hinzufügen“).",
    pasteHint: "Hier einfügen:",
  },
];

function activeSubscribeApp() {
  return SUBSCRIBE_APPS.find((a) => a.id === state.activeApp) || SUBSCRIBE_APPS[0];
}

function currentIcsUrls() {
  const apiUrl = new URL("api/calendar.ics", window.location.href);
  apiUrl.searchParams.set("t", buildSelectionToken());
  return { httpsUrl: apiUrl.href, webcalUrl: apiUrl.href.replace(/^https?:/, "webcal:") };
}

async function copyToClipboard(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (err) {
    // Older browsers without async clipboard support.
    const tmp = document.createElement("textarea");
    tmp.value = text;
    document.body.appendChild(tmp);
    tmp.select();
    document.execCommand("copy");
    document.body.removeChild(tmp);
  }
  btn.textContent = "Kopiert!";
  btn.classList.add("is-copied");
  setTimeout(() => {
    btn.textContent = "Kopieren";
    btn.classList.remove("is-copied");
  }, 1600);
}

function buildUrlRow(url) {
  const row = document.createElement("div");
  row.className = "subscribe-url-row";
  const input = document.createElement("input");
  input.type = "text";
  input.className = "subscribe-url";
  input.readOnly = true;
  input.value = url;
  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "app-copy-btn";
  copyBtn.textContent = "Kopieren";
  copyBtn.addEventListener("click", () => copyToClipboard(url, copyBtn));
  row.append(input, copyBtn);
  return row;
}

function renderAppTabs() {
  const container = document.getElementById("app-tabs");
  container.innerHTML = "";
  for (const app of SUBSCRIBE_APPS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "app-tab" + (state.activeApp === app.id ? " is-active" : "");
    btn.textContent = app.label;
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-selected", String(state.activeApp === app.id));
    btn.addEventListener("click", () => {
      if (state.activeApp === app.id) return;
      state.activeApp = app.id;
      state.fallbackOpen = false;
      renderAppTabs();
      renderAppPanel();
    });
    container.appendChild(btn);
  }
}

function renderAppPanel() {
  const panel = document.getElementById("app-panel");
  panel.innerHTML = "";
  const app = activeSubscribeApp();
  const { httpsUrl, webcalUrl } = currentIcsUrls();

  if (app.direct) {
    const ctaRow = document.createElement("div");
    ctaRow.className = "app-cta-row";
    const cta = document.createElement("a");
    cta.className = "btn app-cta";
    cta.href = webcalUrl;
    cta.textContent = app.ctaLabel;
    const caption = document.createElement("div");
    caption.className = "app-cta-caption";
    caption.textContent = app.caption;
    ctaRow.append(cta, caption);
    panel.appendChild(ctaRow);

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "app-fallback-toggle";
    toggle.textContent = state.fallbackOpen ? "Link ausblenden" : "Button funktioniert nicht? → Link manuell hinzufügen";
    toggle.addEventListener("click", () => {
      state.fallbackOpen = !state.fallbackOpen;
      renderAppPanel();
    });
    panel.appendChild(toggle);

    if (state.fallbackOpen) {
      const box = document.createElement("div");
      box.className = "app-fallback-box";
      const hint = document.createElement("div");
      hint.className = "app-fallback-hint";
      hint.textContent = app.fallbackHint;
      box.appendChild(hint);
      box.appendChild(buildUrlRow(httpsUrl));
      panel.appendChild(box);
    }
  } else {
    if (app.steps && app.steps.length > 0) {
      const stepsEl = document.createElement("div");
      stepsEl.className = "app-steps";
      app.steps.forEach((text, i) => {
        const row = document.createElement("div");
        row.className = "app-step";
        const n = document.createElement("span");
        n.className = "app-step-n";
        n.textContent = String(i + 1);
        const t = document.createElement("span");
        t.textContent = text;
        row.append(n, t);
        stepsEl.appendChild(row);
      });
      panel.appendChild(stepsEl);
    } else if (app.simpleNote) {
      const note = document.createElement("p");
      note.className = "app-simple-note";
      note.textContent = app.simpleNote;
      panel.appendChild(note);
    }
    const pasteHint = document.createElement("div");
    pasteHint.className = "app-paste-hint";
    pasteHint.textContent = app.pasteHint;
    panel.appendChild(pasteHint);
    panel.appendChild(buildUrlRow(httpsUrl));
  }

  const summary = document.createElement("p");
  summary.className = "subscribe-summary";
  summary.appendChild(document.createTextNode(`Dein Kalender enthält: ${selectionSummaryText()}`));
  summary.appendChild(document.createElement("br"));
  // The link itself encodes the selection (stateless by design, see
  // README), so changing the selection later produces a *different* link --
  // the already-subscribed calendar keeps pointing at the old one. Worth
  // saying right here, since this is the only moment it's relevant.
  summary.appendChild(document.createTextNode("Änderst du deine Auswahl später, ändert sich auch dieser Link, der alte muss dann neu abonniert werden."));
  panel.appendChild(summary);
}

function renderSubscribeBar() {
  const placeholder = document.getElementById("subscribe-placeholder");
  const box = document.getElementById("subscribe-box");
  const selected = hasSelection();
  placeholder.hidden = selected;
  box.hidden = !selected;
  if (!selected) {
    updateStickyBarVisibility();
    return;
  }
  renderAppTabs();
  renderAppPanel();
  updateStickySubscribeBar();
}

// --- sticky subscribe bar --------------------------------------------------

// An IntersectionObserver on the filter section (rather than a scroll-offset
// threshold) so the show/hide point tracks the section's real position --
// stays correct regardless of viewport height or content length above it.
let stickyObserver = null;

function updateStickyBarVisibility() {
  document.getElementById("sticky-subscribe-bar").hidden = !(state.stickyVisible && hasSelection());
}

function updateStickySubscribeBar() {
  document.getElementById("sticky-subscribe-summary").textContent = selectionSummaryText();
  updateStickyBarVisibility();
}

function setupStickyBar() {
  const filterSection = document.getElementById("selector-row");

  document.getElementById("sticky-subscribe-link").addEventListener("click", () => {
    filterSection.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  stickyObserver = new IntersectionObserver(
    ([entry]) => {
      // Only "scrolled past" (section above the viewport) counts -- not
      // intersecting because the section is still below (e.g. on load)
      // must not show the bar.
      state.stickyVisible = !entry.isIntersecting && entry.boundingClientRect.top < 0;
      updateStickyBarVisibility();
    },
    { threshold: 0 }
  );
  stickyObserver.observe(filterSection);
}

// The in-progress picker selection (not the finished subscribe link) is kept
// in localStorage so an accidental refresh doesn't wipe out a half-built
// selection -- this is purely client-side and never sent to the server, so
// it doesn't conflict with the "no cookies / no server-side state" design.
const SELECTION_STORAGE_KEY = "sportocal-selection";

function saveSelectionToStorage() {
  try {
    localStorage.setItem(
      SELECTION_STORAGE_KEY,
      JSON.stringify({ clubs: [...state.selectedClubs], raceGroups: [...state.selectedRaceGroups] })
    );
  } catch (err) {
    // Private browsing / quota exceeded -- selection just won't survive a
    // refresh this time, which is exactly the pre-existing behavior.
  }
}

function loadSelectionFromStorage() {
  try {
    const raw = localStorage.getItem(SELECTION_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    state.selectedClubs = new Set(parsed.clubs || []);
    // Older key ("races", pre-group-selection) is intentionally not read --
    // per-race ids wouldn't be valid group keys anyway, so this just starts
    // cycling selection empty for anyone with that stale entry.
    state.selectedRaceGroups = new Set(parsed.raceGroups || []);
  } catch (err) {
    // Malformed/stale entry -- ignore it and start with an empty selection.
  }
}

function refreshSelectionUI() {
  renderFootballCombo();
  renderFootballChips();
  renderCyclingCombo();
  renderCyclingChips();
  renderSubscribeBar();
  updateComboTriggerLabels();
  renderCompetitionFilters();
  saveSelectionToStorage();
  render();
}

// --- combobox open/close wiring ------------------------------------------

function setupCombobox({ triggerId, panelId, doneId, labelId, isOpenKey, emptyLabel, countLabel }) {
  const trigger = document.getElementById(triggerId);
  const panel = document.getElementById(panelId);

  const open = () => {
    state[isOpenKey] = true;
    panel.hidden = false;
  };
  const close = () => {
    state[isOpenKey] = false;
    panel.hidden = true;
  };

  trigger.addEventListener("click", () => (state[isOpenKey] ? close() : open()));
  trigger.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      state[isOpenKey] ? close() : open();
    }
  });
  document.getElementById(doneId).addEventListener("click", close);
  document.addEventListener("click", (e) => {
    if (state[isOpenKey] && !panel.contains(e.target) && !trigger.contains(e.target)) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state[isOpenKey]) close();
  });

  return { open, close };
}

function updateComboTriggerLabels() {
  const footballLabel = document.getElementById("football-combo-trigger-label");
  footballLabel.textContent = state.selectedClubs.size > 0
    ? `${state.selectedClubs.size} Verein${state.selectedClubs.size === 1 ? "" : "e"} ausgewählt`
    : "Vereine suchen und auswählen…";

  const cyclingLabel = document.getElementById("cycling-combo-trigger-label");
  cyclingLabel.textContent = state.selectedRaceGroups.size > 0
    ? `${state.selectedRaceGroups.size} Serie${state.selectedRaceGroups.size === 1 ? "" : "n"} ausgewählt`
    : "Rennserien auswählen…";
}

function setupSelectorUI() {
  setupCombobox({ triggerId: "football-combo-trigger", panelId: "football-combo-panel", doneId: "football-combo-done", isOpenKey: "footballOpen" });
  setupCombobox({ triggerId: "cycling-combo-trigger", panelId: "cycling-combo-panel", doneId: "cycling-combo-done", isOpenKey: "cyclingOpen" });

  const search = document.getElementById("football-search");
  search.addEventListener("input", (e) => {
    state.search = e.target.value;
    renderFootballCombo();
  });

  const cyclingSearch = document.getElementById("cycling-search");
  cyclingSearch.addEventListener("input", (e) => {
    state.cyclingSearch = e.target.value;
    renderCyclingCombo();
  });

  setupStickyBar();

  const footballSublabel = document.getElementById("football-sublabel");
  footballSublabel.textContent = `${state.clubs.length} Vereine aus ${state.leagues.length} Ligen`;
  const cyclingSublabel = document.getElementById("cycling-sublabel");
  cyclingSublabel.textContent = `${state.raceGroups.length} Serien · ${state.races.length} Rennen`;

  refreshSelectionUI();
}

// --- view mode (Nach Wettbewerb / Nach Datum) -----------------------------

const VIEW_STORAGE_KEY = "sportocal-view-mode";

function setupViewToggle() {
  const toggle = document.getElementById("view-toggle");
  const buttons = [...toggle.querySelectorAll(".view-toggle-btn")];
  state.viewMode = localStorage.getItem(VIEW_STORAGE_KEY) || "competition";
  if (!buttons.some((b) => b.dataset.view === state.viewMode)) state.viewMode = "competition";

  const filters = document.getElementById("competition-filters");

  const applyViewMode = () => {
    for (const btn of buttons) {
      const isActive = btn.dataset.view === state.viewMode;
      btn.classList.toggle("is-active", isActive);
      btn.setAttribute("aria-selected", String(isActive));
    }
    filters.classList.toggle("is-hidden", state.viewMode !== "competition");
    render();
  };

  for (const btn of buttons) {
    btn.addEventListener("click", () => {
      state.viewMode = btn.dataset.view;
      localStorage.setItem(VIEW_STORAGE_KEY, state.viewMode);
      applyViewMode();
    });
  }

  applyViewMode();
}

// --- bootstrap -------------------------------------------------------------

async function fetchJson(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status} für ${path}`);
  return res.json();
}

async function main() {
  try {
    const [eventsData, clubs, leagues, raceGroups] = await Promise.all([
      fetchJson("data/events.json"),
      fetchJson("data/clubs.json"),
      fetchJson("data/leagues.json"),
      fetchJson("data/races.json"),
    ]);

    state.events = eventsData.events || [];
    state.clubs = clubs;
    state.clubsById = new Map(clubs.map((c) => [c.id, c]));
    state.leagues = leagues;
    state.raceGroups = raceGroups;
    // Each race is augmented with its group's tier/gender/groupKey client-side
    // (races.json itself stays unchanged, see raceGroupKey()) so visibleEvents()
    // and the chips can go straight from a race to its group without a second lookup.
    state.races = raceGroups.flatMap((group) =>
      group.races.map((race) => ({ ...race, tier: group.tier, gender: group.gender, groupKey: raceGroupKey(group) }))
    );

    loadSelectionFromStorage();
    // Drop any group keys from a stale localStorage entry that no longer
    // match a real group (e.g. races.json changed since it was saved) --
    // otherwise hasSelection() would report a selection that resolves to
    // nothing, silently showing an empty calendar.
    const validGroupKeys = new Set(state.raceGroups.map(raceGroupKey));
    state.selectedRaceGroups = new Set([...state.selectedRaceGroups].filter((key) => validGroupKeys.has(key)));
    setupSelectorUI();
    renderCompetitionFilters();
    setupViewToggle();

    const lastUpdated = document.getElementById("last-updated");
    if (eventsData.generatedAt) {
      const dt = new Date(eventsData.generatedAt);
      lastUpdated.textContent = `Zuletzt aktualisiert: ${dateFormatter.format(dt)} ${timeFormatter.format(dt)} Uhr`;
    }
  } catch (err) {
    document.getElementById("app").innerHTML =
      '<p class="empty-state">Termine konnten nicht geladen werden. Bitte später erneut versuchen.</p>';
    console.error(err);
  }
}

main();
