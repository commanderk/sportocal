const SPORT_LABELS = {
  football: "⚽ Fußball",
  cycling: "🚴 Radsport",
};
const SPORT_ORDER = ["football", "cycling"];

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

const RACE_COLORS = {
  "tour-de-france": "#e8b400",
  "giro-d-italia": "#d81b8f",
  "vuelta-a-espana": "#d92b1c",
  "cyclassics-hamburg": "#0f5fd9",
  "muensterland-giro": "#0a7a6b",
  "deutschland-tour": "#141414",
};

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

// The web view's row-title is a stripped-down label, not the full calendar
// title: no emoji, no competition name, no "Spieltag"/"Etappe" round marker
// -- those are already shown as the section heading and the row-index. The
// full calendar title (with club color/gender emoji) is generated at ICS
// build time from these same raw fields, not stored on the event.
function eventDisplayTitle(event) {
  if (event.sport === "football") {
    return [event.homeTeamName, event.awayTeamName].filter(Boolean).join(" – ");
  }
  if (event.route) {
    return `${event.route.start} → ${event.route.finish}`;
  }
  return event.competition;
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
  row.className = "event-row" + (isPastEvent(event) ? " is-past" : "");

  const idx = document.createElement("div");
  idx.className = "row-index";
  idx.textContent = extractRoundNumber(event.round);
  row.appendChild(idx);

  const dateCol = document.createElement("div");
  dateCol.className = "row-date";
  dateCol.innerHTML = `${weekdayFormatter.format(startDate)}<span class="row-daynum">${formatShortDate(startDate)}</span>`;
  row.appendChild(dateCol);

  const timeCol = document.createElement("div");
  timeCol.className = "row-time";
  timeCol.textContent = event.timeConfirmed && !isAllDay(event.start)
    ? timeFormatter.format(startDate)
    : "tbd";
  row.appendChild(timeCol);

  const logos = document.createElement("div");
  logos.className = "row-logos";
  if (event.homeTeamLogo) {
    logos.appendChild(Object.assign(document.createElement("img"), { src: event.homeTeamLogo, alt: "", loading: "lazy" }));
  }
  if (event.awayTeamLogo) {
    logos.appendChild(Object.assign(document.createElement("img"), { src: event.awayTeamLogo, alt: "", loading: "lazy" }));
  }
  row.appendChild(logos);

  const title = document.createElement("div");
  title.className = "row-title";
  title.textContent = eventDisplayTitle(event);
  row.appendChild(title);

  // Cycling rows already show the route (start → finish) as the title, so
  // repeating it in the venue column would just duplicate the same text.
  const venue = document.createElement("div");
  venue.className = "row-venue";
  venue.textContent = event.route ? "" : event.location || "";
  row.appendChild(venue);

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

    const visibleNames = competitionFilter === FILTER_ALL
      ? competitionNames
      : competitionNames.filter((name) => name === competitionFilter);
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

function getCompetitionNamesInOrder(events) {
  const bySport = groupBy(events, (e) => e.sport);
  const sportKeys = [...bySport.keys()].sort((a, b) => SPORT_ORDER.indexOf(a) - SPORT_ORDER.indexOf(b));
  return sportKeys.flatMap((sport) => [...groupBy(bySport.get(sport), (e) => e.competition).keys()].sort());
}

function renderCompetitionFilters() {
  const container = document.getElementById("competition-filters");
  container.innerHTML = "";
  const names = [FILTER_ALL, ...getCompetitionNamesInOrder(visibleEvents())];
  if (!names.includes(state.competitionFilter)) state.competitionFilter = FILTER_ALL;
  for (const name of names) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "filter-pill" + (state.competitionFilter === name ? " is-active" : "");
    btn.textContent = name;
    btn.addEventListener("click", () => {
      state.competitionFilter = name;
      renderCompetitionFilters();
      render();
    });
    container.appendChild(btn);
  }
}

const state = {
  events: [],
  clubs: [],
  clubsById: new Map(),
  leagues: [],
  races: [],
  viewMode: "competition",
  competitionFilter: FILTER_ALL,
  selectedClubs: new Set(), // tokens "<clubId>:<gender>"
  selectedRaces: new Set(), // race ids
  footballOpen: false,
  cyclingOpen: false,
  search: "",
};

// --- selection-aware event list ----------------------------------------

function hasSelection() {
  return state.selectedClubs.size > 0 || state.selectedRaces.size > 0;
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
      return race && state.selectedRaces.has(race.id);
    }
    return false;
  });
}

function render() {
  const app = document.getElementById("app");
  app.innerHTML = "";

  const events = visibleEvents();
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
    head.className = "league-group-head";
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

function renderCyclingCombo() {
  const body = document.getElementById("cycling-combo-body");
  body.innerHTML = "";
  for (const race of state.races) {
    const color = RACE_COLORS[race.id] || "#141414";
    const row = document.createElement("label");
    row.className = "race-row";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selectedRaces.has(race.id);
    checkbox.style.accentColor = color;
    checkbox.addEventListener("change", () => {
      if (state.selectedRaces.has(race.id)) state.selectedRaces.delete(race.id);
      else state.selectedRaces.add(race.id);
      refreshSelectionUI();
    });
    const swatch = document.createElement("span");
    swatch.className = "race-swatch";
    swatch.style.background = color;
    const name = document.createElement("span");
    name.textContent = race.name;
    row.append(checkbox, swatch, name);
    body.appendChild(row);
  }
}

function renderCyclingChips() {
  const container = document.getElementById("cycling-chips");
  container.innerHTML = "";
  for (const raceId of state.selectedRaces) {
    const race = state.races.find((r) => r.id === raceId);
    if (!race) continue;
    const color = RACE_COLORS[raceId] || "#141414";
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.style.background = color;
    chip.style.color = contrastText(color);
    const name = document.createElement("span");
    name.textContent = race.name;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "✕";
    remove.addEventListener("click", () => {
      state.selectedRaces.delete(raceId);
      refreshSelectionUI();
    });
    chip.append(name, remove);
    container.appendChild(chip);
  }
  document.getElementById("cycling-empty-hint").hidden = state.selectedRaces.size > 0;
}

// --- subscribe bar --------------------------------------------------------

function buildSelectionToken() {
  const clubTokens = [...state.selectedClubs];
  const raceTokens = [...state.selectedRaces].map((id) => `race:${id}`);
  return [...clubTokens, ...raceTokens].join(",");
}

function selectionSummaryText() {
  const clubNames = [...state.selectedClubs]
    .map((t) => state.clubsById.get(t.split(":")[0]))
    .filter(Boolean)
    .map((c) => c.name);
  const raceNames = [...state.selectedRaces]
    .map((id) => state.races.find((r) => r.id === id))
    .filter(Boolean)
    .map((r) => r.name);
  return [...clubNames, ...raceNames].join(", ");
}

function renderSubscribeBar() {
  const placeholder = document.getElementById("subscribe-placeholder");
  const active = document.getElementById("subscribe-active");
  const selected = hasSelection();
  placeholder.hidden = selected;
  active.hidden = !selected;
  if (!selected) return;

  const token = buildSelectionToken();
  const apiUrl = new URL("api/calendar.ics", window.location.href);
  apiUrl.searchParams.set("t", token);

  document.getElementById("webcal-link").href = apiUrl.href.replace(/^https?:/, "webcal:");
  document.getElementById("https-url").value = apiUrl.href;
  document.getElementById("subscribe-summary").textContent = `Dein Kalender enthält: ${selectionSummaryText()}`;
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
      JSON.stringify({ clubs: [...state.selectedClubs], races: [...state.selectedRaces] })
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
    state.selectedRaces = new Set(parsed.races || []);
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
  cyclingLabel.textContent = state.selectedRaces.size > 0
    ? `${state.selectedRaces.size} Rennen ausgewählt`
    : "Rennen auswählen…";
}

function setupSelectorUI() {
  setupCombobox({ triggerId: "football-combo-trigger", panelId: "football-combo-panel", doneId: "football-combo-done", isOpenKey: "footballOpen" });
  setupCombobox({ triggerId: "cycling-combo-trigger", panelId: "cycling-combo-panel", doneId: "cycling-combo-done", isOpenKey: "cyclingOpen" });

  const search = document.getElementById("football-search");
  search.addEventListener("input", (e) => {
    state.search = e.target.value;
    renderFootballCombo();
  });

  document.getElementById("copy-url-btn").addEventListener("click", async () => {
    const input = document.getElementById("https-url");
    const btn = document.getElementById("copy-url-btn");
    try {
      await navigator.clipboard.writeText(input.value);
    } catch (err) {
      input.select();
      document.execCommand("copy");
    }
    btn.textContent = "Kopiert!";
    btn.classList.add("is-copied");
    setTimeout(() => {
      btn.textContent = "Kopieren";
      btn.classList.remove("is-copied");
    }, 1600);
  });

  const footballSublabel = document.getElementById("football-sublabel");
  footballSublabel.textContent = `${state.clubs.length} Vereine aus ${state.leagues.length} Liga-Gruppen`;
  const cyclingSublabel = document.getElementById("cycling-sublabel");
  cyclingSublabel.textContent = `${state.races.length} Rennen`;

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
    const [eventsData, clubs, leagues, races] = await Promise.all([
      fetchJson("data/events.json"),
      fetchJson("data/clubs.json"),
      fetchJson("data/leagues.json"),
      fetchJson("data/races.json"),
    ]);

    state.events = eventsData.events || [];
    state.clubs = clubs;
    state.clubsById = new Map(clubs.map((c) => [c.id, c]));
    state.leagues = leagues;
    state.races = races;

    loadSelectionFromStorage();
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
