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
const dayFormatter = new Intl.DateTimeFormat("de-DE", { day: "2-digit", timeZone: "Europe/Berlin" });
const monthFormatter = new Intl.DateTimeFormat("de-DE", { month: "short", timeZone: "Europe/Berlin" });

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
// sorting and graying out cards. Comparison is by calendar day in
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

function renderEventCard(event, { showCompetitionTag = false } = {}) {
  const card = document.createElement("div");
  const startDate = parseStart(event.start);
  card.className = "event-card" + (isPastEvent(event) ? " is-past" : "");

  const dateBox = document.createElement("div");
  dateBox.className = "event-date";
  dateBox.innerHTML = `<span class="day">${dayFormatter.format(startDate)}</span><span class="month">${monthFormatter.format(startDate)}</span>`;
  card.appendChild(dateBox);

  if (event.participants) {
    const logos = document.createElement("div");
    logos.className = "event-logos";
    for (const side of ["home", "away"]) {
      const p = event.participants[side];
      if (p && p.logo) {
        const img = document.createElement("img");
        img.src = p.logo;
        img.alt = p.shortName || p.name || "";
        img.loading = "lazy";
        logos.appendChild(img);
      }
    }
    card.appendChild(logos);
  } else {
    const emoji = document.createElement("div");
    emoji.className = "event-emoji";
    emoji.textContent = "🚴";
    card.appendChild(emoji);
  }

  const body = document.createElement("div");
  body.className = "event-body";

  if (showCompetitionTag) {
    const tag = document.createElement("div");
    tag.className = "event-competition-tag";
    tag.textContent = `${SPORT_LABELS[event.sport] || event.sport} · ${event.competition}`;
    body.appendChild(tag);
  }

  const title = document.createElement("div");
  title.className = "event-title";
  title.textContent = event.title;
  if (!event.timeConfirmed) {
    const badge = document.createElement("span");
    badge.className = "time-badge";
    badge.textContent = "Uhrzeit noch nicht final";
    title.appendChild(badge);
  }
  body.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "event-meta";
  const metaParts = [];
  if (!isAllDay(event.start) && event.timeConfirmed) {
    metaParts.push(timeFormatter.format(startDate) + " Uhr");
  }
  if (event.location) metaParts.push(event.location);
  meta.textContent = metaParts.join(" · ");
  if (metaParts.length) body.appendChild(meta);

  card.appendChild(body);
  return card;
}

function renderCompetitionGroup(competitionName, events) {
  const upcoming = events.filter((e) => !isPastEvent(e)).sort((a, b) => a.start.localeCompare(b.start));
  const past = events.filter((e) => isPastEvent(e)).sort((a, b) => b.start.localeCompare(a.start));

  const section = document.createElement("div");
  section.className = "competition-group";
  const heading = document.createElement("h3");
  heading.textContent = competitionName;
  section.appendChild(heading);

  if (upcoming.length === 0 && past.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Keine Termine bekannt.";
    section.appendChild(empty);
    return section;
  }

  for (const event of upcoming) {
    section.appendChild(renderEventCard(event));
  }

  // Every group applies the exact same rule: upcoming first (bright), then a
  // labelled divider, then past events (grayed) -- so it's always visible
  // *why* a card is grayed, whether a group has one past match or a whole
  // finished season.
  if (past.length > 0) {
    const divider = document.createElement("p");
    divider.className = "past-divider";
    divider.textContent =
      upcoming.length > 0
        ? "Vergangene Termine"
        : "Vergangene Termine (noch keine kommenden Termine bekannt)";
    section.appendChild(divider);
    for (const event of past) {
      section.appendChild(renderEventCard(event));
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
    section.appendChild(renderEventCard(event, { showCompetitionTag: true }));
  }
  if (past.length > 0) {
    const divider = document.createElement("p");
    divider.className = "past-divider";
    divider.textContent = "Vergangene Termine";
    section.appendChild(divider);
    for (const event of past) {
      section.appendChild(renderEventCard(event, { showCompetitionTag: true }));
    }
  }
  app.appendChild(section);
}

function renderByCompetition(events, app) {
  const bySport = groupBy(events, (e) => e.sport);
  const sportKeys = [...bySport.keys()].sort(
    (a, b) => SPORT_ORDER.indexOf(a) - SPORT_ORDER.indexOf(b)
  );

  for (const sport of sportKeys) {
    const sportEvents = bySport.get(sport);
    const sportSection = document.createElement("section");
    sportSection.className = "sport-section";
    const h2 = document.createElement("h2");
    h2.textContent = SPORT_LABELS[sport] || sport;
    sportSection.appendChild(h2);

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

    for (const competitionName of competitionNames) {
      sportSection.appendChild(renderCompetitionGroup(competitionName, byCompetition.get(competitionName)));
    }
    app.appendChild(sportSection);
  }
}

function render(events, viewMode) {
  const app = document.getElementById("app");
  app.innerHTML = "";

  if (events.length === 0) {
    app.innerHTML = '<p class="empty-state">Noch keine Termine geladen.</p>';
    return;
  }

  if (viewMode === "date") {
    renderByDate(events, app);
  } else {
    renderByCompetition(events, app);
  }
}

const VIEW_STORAGE_KEY = "sportocal-view-mode";

function setupViewToggle(events) {
  const toggle = document.getElementById("view-toggle");
  const buttons = [...toggle.querySelectorAll(".view-toggle-btn")];
  let viewMode = localStorage.getItem(VIEW_STORAGE_KEY) || "competition";
  if (!buttons.some((b) => b.dataset.view === viewMode)) viewMode = "competition";

  const applyViewMode = () => {
    for (const btn of buttons) {
      const isActive = btn.dataset.view === viewMode;
      btn.classList.toggle("is-active", isActive);
      btn.setAttribute("aria-selected", String(isActive));
    }
    render(events, viewMode);
  };

  for (const btn of buttons) {
    btn.addEventListener("click", () => {
      viewMode = btn.dataset.view;
      localStorage.setItem(VIEW_STORAGE_KEY, viewMode);
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
    setupViewToggle(data.events || []);
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
