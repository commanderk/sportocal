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

function groupBy(items, keyFn) {
  const map = new Map();
  for (const item of items) {
    const key = keyFn(item);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(item);
  }
  return map;
}

function renderEventCard(event) {
  const card = document.createElement("div");
  const startDate = parseStart(event.start);
  const now = new Date();
  card.className = "event-card" + (startDate < now ? " is-past" : "");

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
  const now = new Date();
  const upcoming = events.filter((e) => parseStart(e.start) >= now).sort((a, b) => a.start.localeCompare(b.start));
  const past = events.filter((e) => parseStart(e.start) < now).sort((a, b) => b.start.localeCompare(a.start));
  const ordered = [...upcoming, ...past];

  const section = document.createElement("div");
  section.className = "competition-group";
  const heading = document.createElement("h3");
  heading.textContent = competitionName;
  section.appendChild(heading);

  if (ordered.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Keine Termine bekannt.";
    section.appendChild(empty);
  } else {
    for (const event of ordered) {
      section.appendChild(renderEventCard(event));
    }
  }
  return section;
}

function render(events) {
  const app = document.getElementById("app");
  app.innerHTML = "";

  if (events.length === 0) {
    app.innerHTML = '<p class="empty-state">Noch keine Termine geladen.</p>';
    return;
  }

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
      const now = new Date();
      const future = evts.filter((e) => parseStart(e.start) >= now);
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

async function main() {
  setupSubscribeLinks();
  try {
    const res = await fetch("data/events.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    render(data.events || []);
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
