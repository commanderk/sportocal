const SPORT_LABELS = {
  football: "⚽ Fußball",
  cycling: "🚴 Radsport",
};
const SPORT_ORDER = ["football", "cycling"];

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
// -- those are already shown as the section heading and the row-index. Only
// `event.title` (used for the .ics export) keeps the full descriptive text.
function eventDisplayTitle(event) {
  if (event.participants) {
    const home = event.participants.home;
    const away = event.participants.away;
    const homeName = (home && (home.shortName || home.name)) || "";
    const awayName = (away && (away.shortName || away.name)) || "";
    return [homeName, awayName].filter(Boolean).join(" – ");
  }
  if (event.route) {
    return `${event.route.start} → ${event.route.finish}`;
  }
  return event.title;
}

function setupSubscribeLinks() {
  const icsUrl = new URL("kalender.ics", window.location.href);
  document.getElementById("https-link").href = icsUrl.href;
  document.getElementById("webcal-link").href = icsUrl.href.replace(/^https?:/, "webcal:");
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
  if (event.participants) {
    const home = event.participants.home;
    const away = event.participants.away;
    if (home && home.logo) {
      logos.appendChild(Object.assign(document.createElement("img"), { src: home.logo, alt: "", loading: "lazy" }));
    }
    if (away && away.logo) {
      logos.appendChild(Object.assign(document.createElement("img"), { src: away.logo, alt: "", loading: "lazy" }));
    }
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
  const names = [FILTER_ALL, ...getCompetitionNamesInOrder(state.events)];
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

const state = { events: [], viewMode: "competition", competitionFilter: FILTER_ALL };

function render() {
  const app = document.getElementById("app");
  app.innerHTML = "";

  if (state.events.length === 0) {
    app.innerHTML = '<p class="empty-state">Noch keine Termine geladen.</p>';
    return;
  }

  if (state.viewMode === "date") {
    renderByDate(state.events, app);
  } else {
    renderByCompetition(state.events, app, state.competitionFilter);
  }
}

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

async function main() {
  setupSubscribeLinks();
  try {
    const res = await fetch("data/events.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.events = data.events || [];
    document.getElementById("count-label").textContent = `${state.events.length} Termine`;
    renderCompetitionFilters();
    setupViewToggle();
    const lastUpdated = document.getElementById("last-updated");
    if (data.generatedAt) {
      const dt = new Date(data.generatedAt);
      lastUpdated.textContent = `Zuletzt aktualisiert: ${dateFormatter.format(dt)} ${timeFormatter.format(dt)} Uhr`;
    }
  } catch (err) {
    document.getElementById("app").innerHTML =
      '<p class="empty-state">Termine konnten nicht geladen werden. Bitte später erneut versuchen.</p>';
    console.error(err);
  }
}

main();
