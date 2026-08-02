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

// Per-race color accent for cycling event rows (see createRaceBadge()) --
// the picker itself moved to group-level selection (see renderCyclingCombo()),
// so this is no longer used there, but individual event rows still need a
// per-race color the way football rows use a club's colorHex. These are real
// logo-derived hex values. Any race id without an entry here falls back to
// #141414 in createRaceBadge(), same convention RACE_GROUP_COLORS uses --
// several men's one-day classics have no entry at all (only their women's
// counterpart does), so they'll share that fallback color rather than each
// getting a distinct one.
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

// Stable key identifying a full football league×gender selection -- same
// "<id>:<gender>" shape club tokens already use, so it slots into the same
// URL-token/localStorage patterns as selectedClubs and selectedRaceGroups.
// A league is inherently single-gender in this app's data (see
// leagues.json), so the gender suffix is redundant with league.id alone,
// but kept for consistency with raceGroupKey()'s tier+gender shape and
// buildSelectionToken()'s "prefix:<key>" convention.
function leagueGroupKey(league) {
  return `${league.id}:${league.gender}`;
}

// Every club currently in `league`, unfiltered by search -- the group-token
// semantics ("whole league, whoever's in it") always apply to the full
// roster. Shared by renderFootballCombo() (which rows to show / whether the
// master checkbox is fully/partially checked) and
// consolidateFullyCoveredLeagueGroups() (whether an individual-token
// selection now covers the whole league).
function clubsInLeague(league) {
  return state.clubs.filter((c) => c.teams[league.gender] && c.teams[league.gender].league === league.competition);
}

const GENDER_LABELS = { men: "Männer", women: "Frauen" };

// league.competition names don't share one consistent shape: the women's
// leagues carry an explicit "Frauen-" marker ("Frauen-Bundesliga",
// "2. Frauen-Bundesliga") while the men's counterpart of the top flight has
// no "1. " prefix at all ("Bundesliga", not "1. Bundesliga") -- unlike every
// other tier, which is already numbered. Stripping "Frauen-" and then
// backfilling "1. " only for the bare "Bundesliga" case turns both of those
// into the same canonical "<n>. Bundesliga" shape as 2./3. Liga already
// have, so leagueGroupLabel() below can append gender uniformly instead of
// hand-listing all six league×gender combinations.
function canonicalLeagueName(competition) {
  const name = competition.replace(/Frauen-/, "");
  return name === "Bundesliga" ? `1. ${name}` : name;
}

// Base label for a full league-group selection, e.g. "1. Bundesliga
// Männer" -- gender is spelled out explicitly since canonicalLeagueName()
// alone doesn't always make it obvious (the men's leagues carry no gender
// marker). No "(Alle Vereine)" suffix here so this stays reusable wherever
// that phrasing wouldn't fit -- callers that mean the full-league selection
// append it themselves (see renderFootballCombo(), renderFootballChips()).
function leagueGroupLabel(league) {
  return `${canonicalLeagueName(league.competition)} ${GENDER_LABELS[league.gender] || league.gender}`;
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

// A "-ii" club (e.g. vfb-stuttgart-ii) is the same club's second team, same
// crest/colors as the main entry -- clubs.json currently gives it its own
// shortName ("VfB II") for list/filter labels, but the row badge should read
// identically to the first team's badge (color + Kürzel), with the II vs.
// non-II distinction carried by the full team name text next to it instead.
// Deriving the base id here (rather than editing clubs.json) keeps this
// generic for any future "-ii" entry without per-club special-casing.
function resolveBadgeClub(teamId) {
  if (!teamId) return null;
  const club = state.clubsById.get(teamId);
  if (!club) return null;
  if (teamId.endsWith("-ii")) {
    const baseClub = state.clubsById.get(teamId.slice(0, -3));
    if (baseClub) return baseClub;
  }
  return club;
}

// Circular color+Kürzel badge replacing the old hotlinked crest <img> (the
// homeTeamLogo/awayTeamLogo fields still exist in events.json but are no
// longer rendered) -- avoids dead links and crest copyright/trademark issues
// from hotlinking third-party logo URLs.
// shortName is used as-is (already unambiguous per club, unlike car-plate-style
// city codes: VfB Stuttgart vs. Stuttgarter Kickers, or the three Köln clubs,
// would collide under a city-code scheme). Teams with no clubs.json match
// (homeTeamId/awayTeamId null, or an opponent without its own entry, e.g. a
// lower-league cup opponent) fall back to a neutral gray badge with the first
// two letters of the raw team name.
function createClubBadge(teamId, teamName) {
  const badge = document.createElement("span");
  badge.className = "club-badge";
  const club = resolveBadgeClub(teamId);
  if (club) {
    badge.style.background = club.colorHex;
    badge.style.color = contrastText(club.colorHex);
    badge.textContent = club.shortName;
  } else {
    badge.classList.add("club-badge-fallback");
    badge.textContent = (teamName || "").trim().slice(0, 2).toUpperCase() || "?";
  }
  return badge;
}

// Cycling counterpart to createClubBadge() -- same visual system, same
// .club-badge CSS class (no second badge system), just a different color/
// text source: RACE_COLORS (see comment there) keyed by race id, and
// race.shortName (config.json -> races.json, see build_site_data.py).
// Matching on name alone is ambiguous: several men's/women's pairs share
// the exact same race name (e.g. "Ronde Van Brugge", see
// computeDuplicateOneDayCompetitions()), so name+gender together is the
// actual unique key here. NOTE: visibleEvents()'s race lookup (for group
// filtering) still matches on name only and inherits the same ambiguity --
// since men's groups sort before women's (GENDER_ORDER in
// build_site_data.py), a name-colliding women's event there silently
// resolves to the men's race's groupKey, so it can show up under the wrong
// tier×gender filter. Pre-existing, not introduced here; left as-is since
// fixing it is a filtering-behavior change outside this task's scope.
// Unlike club badges there's no per-race fallback color needed -- RACE_COLORS
// itself already falls back to #141414 for any race without its own entry,
// so every race gets a real color, just not always a distinct one.
function createRaceBadge(event) {
  const race = state.races.find((r) => r.name === event.competition && r.gender === event.gender);
  const color = (race && RACE_COLORS[race.id]) || "#141414";
  const badge = document.createElement("span");
  badge.className = "club-badge";
  badge.style.background = color;
  badge.style.color = contrastText(color);
  badge.textContent = (race && race.shortName) || "?";
  return badge;
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
  if (event.round) {
    return `${event.competition}, ${event.round}`;
  }
  if (duplicateOneDayCompetitions.has(event.competition)) {
    return `${event.competition} ${event.start.slice(0, 4)}`;
  }
  return event.competition;
}

// route.typeDisplay is the German translation build_site_data.py already
// computes server-side (see STAGE_TYPE_DISPLAY_DE / normalize_stage_type()
// in scripts/common.py) -- the client no longer needs its own copy of that
// translation table or the "Mountain stage" vs. "Mountain" suffix-stripping
// normalization, both now live in exactly one place. Falls back to the raw
// route.type (untranslated, possibly still suffixed) only for an
// events.json snapshot generated before typeDisplay existed.
function stageTypeLabel(route) {
  if (!route) return null;
  return route.typeDisplay || route.type || null;
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
    (event.sport === "cycling" ? " event-row--cycling" : "") +
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
  const stageType = stageTypeLabel(event.route);

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

  const title = document.createElement("div");
  title.className = "row-title";
  if (event.sport === "football") {
    title.appendChild(createClubBadge(event.homeTeamId, event.homeTeamName));
    const homeName = document.createElement("span");
    homeName.className = "row-title-text";
    homeName.textContent = event.homeTeamName || "";
    title.appendChild(homeName);
    const sep = document.createElement("span");
    sep.className = "row-title-sep";
    sep.textContent = "–";
    title.appendChild(sep);
    title.appendChild(createClubBadge(event.awayTeamId, event.awayTeamName));
    const awayName = document.createElement("span");
    awayName.className = "row-title-text";
    awayName.textContent = event.awayTeamName || "";
    title.appendChild(awayName);
  } else {
    title.appendChild(createRaceBadge(event));
    const text = document.createElement("span");
    text.className = "row-title-text";
    text.textContent = titleText;
    title.appendChild(text);
  }
  desktop.appendChild(title);

  const venue = document.createElement("div");
  venue.className = "row-venue";
  const venueMain = document.createElement("span");
  venueMain.className = "row-venue-text";
  venueMain.textContent = venueText;
  venue.appendChild(venueMain);
  if (stageType) {
    const typeEl = document.createElement("span");
    typeEl.className = "row-venue-type";
    typeEl.textContent = stageType;
    venue.appendChild(typeEl);
  }
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
    mobileMain.appendChild(createClubBadge(event.homeTeamId, event.homeTeamName));
    const home = document.createElement("span");
    home.className = "row-mobile-team";
    home.textContent = event.homeTeamName || "";
    mobileMain.appendChild(home);
    const sep = document.createElement("span");
    sep.className = "row-mobile-sep";
    sep.textContent = "–";
    mobileMain.appendChild(sep);
    mobileMain.appendChild(createClubBadge(event.awayTeamId, event.awayTeamName));
    const away = document.createElement("span");
    away.className = "row-mobile-team";
    away.textContent = event.awayTeamName || "";
    mobileMain.appendChild(away);
  } else {
    mobileMain.appendChild(createRaceBadge(event));
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
    stageType,
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
    for (const key of state.selectedLeagueGroups) {
      const league = state.leagues.find((l) => leagueGroupKey(l) === key);
      if (league) selectedLeagueNames.add(league.competition);
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
  selectedLeagueGroups: new Set(), // "<leagueId>:<gender>" keys, see leagueGroupKey() -- "whole league, whoever's in it" selection, analogous to selectedRaceGroups
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
  return state.selectedClubs.size > 0 || state.selectedRaceGroups.size > 0 || state.selectedLeagueGroups.size > 0;
}

// A league-group selection ("Alle Vereine der <Liga> auswählen", see
// renderFootballCombo()) means "whoever's currently in this league", not a
// snapshot of today's clubs -- so membership is checked live against
// club.teams[gender].league here, never against a stored club-id list. This
// is also what pulls a member club's cup/UEFA fixtures in automatically:
// membership only depends on the club (via homeTeamId/awayTeamId), never on
// event.competition itself, so a DFB-Pokal match is included the same way a
// league match is, no special-casing needed.
// `gender` must be the *event's* gender, and is compared against the
// league's own gender (not just "does the club have any team in that
// league") -- a club fielding both a men's and a women's team (e.g. 1. FC
// Köln) must not have its women's fixtures pulled in by a men's-league
// group selection just because the club also has a men's team somewhere.
function clubMatchesAnySelectedLeagueGroup(clubId, gender) {
  if (!clubId) return false;
  const club = state.clubsById.get(clubId);
  if (!club) return false;
  for (const key of state.selectedLeagueGroups) {
    const league = state.leagues.find((l) => leagueGroupKey(l) === key);
    if (!league || league.gender !== gender) continue;
    const team = club.teams[league.gender];
    if (team && team.league === league.competition) return true;
  }
  return false;
}

// Without a selection the list is an unfiltered preview of everything, same
// spirit as the design mock -- so the page is never empty on first load.
function visibleEvents() {
  if (!hasSelection()) return state.events;
  return state.events.filter((e) => {
    if (e.sport === "football") {
      return (
        state.selectedClubs.has(`${e.homeTeamId}:${e.gender}`) ||
        state.selectedClubs.has(`${e.awayTeamId}:${e.gender}`) ||
        clubMatchesAnySelectedLeagueGroup(e.homeTeamId, e.gender) ||
        clubMatchesAnySelectedLeagueGroup(e.awayTeamId, e.gender)
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
    // Unfiltered league roster -- the group-token semantics ("whole league,
    // whoever's in it") always apply to *every* club in the league, never
    // just whatever a search happens to currently show. `clubs` (search-
    // filtered) is only used for which rows to render and, while a search is
    // active, for the pre-existing "select the filtered subset" fallback.
    const leagueClubs = clubsInLeague(league).sort((a, b) => a.name.localeCompare(b.name, "de"));
    const clubs = leagueClubs.filter(clubMatchesSearch);
    if (clubs.length === 0) continue;

    const key = leagueGroupKey(league);
    const groupSelected = state.selectedLeagueGroups.has(key);
    const color = LEAGUE_COLORS[league.id] || "#141414";
    const fullTokens = leagueClubs.map((c) => `${c.id}:${league.gender}`);
    const tokens = clubs.map((c) => `${c.id}:${league.gender}`);
    const selectedCount = fullTokens.filter((t) => state.selectedClubs.has(t)).length;
    const allSelected = groupSelected || selectedCount === fullTokens.length;
    const someSelected = !allSelected && selectedCount > 0;

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
      if (allSelected) {
        // Full deselect (whether it was a group token or a fully-itemized
        // league) -- no group token, no individual tokens left for this league.
        state.selectedLeagueGroups.delete(key);
        fullTokens.forEach((t) => state.selectedClubs.delete(t));
      } else if (!state.search.trim()) {
        // Consolidate into a single group token ("whoever's in the league",
        // not today's roster) -- drop any partial individual tokens so the
        // selection has exactly one representation, never both at once.
        state.selectedLeagueGroups.add(key);
        fullTokens.forEach((t) => state.selectedClubs.delete(t));
      } else {
        // Search is narrowing the visible rows -- "select all" here can only
        // reasonably mean the filtered subset, not the whole league, so this
        // stays individual-token selection (pre-existing behavior).
        tokens.forEach((t) => state.selectedClubs.add(t));
      }
      refreshSelectionUI();
    });
    const swatch = document.createElement("span");
    swatch.className = "league-swatch";
    swatch.style.background = color;
    const name = document.createElement("span");
    name.className = "league-group-name";
    name.textContent = `${leagueGroupLabel(league)} (Alle Vereine)`;
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
      checkbox.checked = state.selectedClubs.has(token) || groupSelected;
      checkbox.addEventListener("change", () => {
        if (state.selectedLeagueGroups.has(key)) {
          // This club's checked state currently comes from the league's
          // group token, not an individual token -- unchecking it means
          // "everyone in the league except this one", so explode the group
          // token into individual tokens for every other member
          // (gender-specific, full roster regardless of search) and drop
          // the group token itself. Checking-while-group-selected can't
          // happen -- it's already checked, a click can only uncheck it.
          state.selectedLeagueGroups.delete(key);
          for (const c of leagueClubs) {
            if (c.id === club.id) continue;
            state.selectedClubs.add(`${c.id}:${league.gender}`);
          }
        } else if (state.selectedClubs.has(token)) {
          state.selectedClubs.delete(token);
        } else {
          state.selectedClubs.add(token);
        }
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

  for (const key of state.selectedLeagueGroups) {
    const league = state.leagues.find((l) => leagueGroupKey(l) === key);
    if (!league) continue;
    const color = LEAGUE_COLORS[league.id] || "#141414";
    const chip = document.createElement("div");
    chip.className = "chip";
    chip.style.background = color;
    chip.style.color = contrastText(color);
    const name = document.createElement("span");
    name.textContent = `${leagueGroupLabel(league)} (Alle Vereine)`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "✕";
    remove.addEventListener("click", () => {
      state.selectedLeagueGroups.delete(key);
      refreshSelectionUI();
    });
    chip.append(name, remove);
    container.appendChild(chip);
  }

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
  document.getElementById("football-empty-hint").hidden = state.selectedClubs.size > 0 || state.selectedLeagueGroups.size > 0;
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
  const leagueGroupTokens = [...state.selectedLeagueGroups].map((key) => `league:${key}`);
  const raceGroupTokens = [...state.selectedRaceGroups].map((key) => `raceGroup:${key}`);
  return [...clubTokens, ...leagueGroupTokens, ...raceGroupTokens].join(",");
}

function selectionSummaryText() {
  const clubNames = [...state.selectedClubs]
    .map((t) => state.clubsById.get(t.split(":")[0]))
    .filter(Boolean)
    .map((c) => c.name);
  const leagueGroupNames = [...state.selectedLeagueGroups]
    .map((key) => state.leagues.find((l) => leagueGroupKey(l) === key))
    .filter(Boolean)
    .map((l) => `${leagueGroupLabel(l)} (Alle Vereine)`);
  const raceGroupNames = [...state.selectedRaceGroups]
    .map((key) => state.raceGroups.find((g) => raceGroupKey(g) === key))
    .filter(Boolean)
    .map((g) => g.label);
  return [...clubNames, ...leagueGroupNames, ...raceGroupNames].join(", ");
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
      JSON.stringify({
        clubs: [...state.selectedClubs],
        raceGroups: [...state.selectedRaceGroups],
        leagueGroups: [...state.selectedLeagueGroups],
      })
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
    state.selectedLeagueGroups = new Set(parsed.leagueGroups || []);
  } catch (err) {
    // Malformed/stale entry -- ignore it and start with an empty selection.
  }
}

// A league whose individually-selected clubs happen to add up to its whole
// current roster is equivalent to a group selection -- collapse those
// tokens into the single league-group token so the checkbox/chip reflect
// that consistently. Re-derived from scratch on every selection change
// (called from refreshSelectionUI()) by comparing the current selectedClubs
// set against the league's full roster, rather than relying on a flag set
// only when the master "select all" checkbox itself is clicked -- so
// manually re-checking the one club that was missing (regardless of which
// club, or the order individual clubs were (re-)checked in) also collapses
// back to the group chip, not just a fresh individual chip alongside it.
function consolidateFullyCoveredLeagueGroups() {
  for (const league of state.leagues) {
    const key = leagueGroupKey(league);
    if (state.selectedLeagueGroups.has(key)) continue;
    const fullTokens = clubsInLeague(league).map((c) => `${c.id}:${league.gender}`);
    if (fullTokens.length > 0 && fullTokens.every((t) => state.selectedClubs.has(t))) {
      state.selectedLeagueGroups.add(key);
      fullTokens.forEach((t) => state.selectedClubs.delete(t));
    }
  }
}

function refreshSelectionUI() {
  consolidateFullyCoveredLeagueGroups();
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
  const leagueCount = state.selectedLeagueGroups.size;
  const clubCount = state.selectedClubs.size;
  if (leagueCount === 0 && clubCount === 0) {
    footballLabel.textContent = "Vereine suchen und auswählen…";
  } else {
    const parts = [];
    if (leagueCount > 0) parts.push(`${leagueCount} Liga${leagueCount === 1 ? "" : "en"}`);
    if (clubCount > 0) parts.push(`${clubCount} Verein${clubCount === 1 ? "" : "e"}`);
    footballLabel.textContent = `${parts.join(" + ")} ausgewählt`;
  }

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
    const validLeagueGroupKeys = new Set(state.leagues.map(leagueGroupKey));
    state.selectedLeagueGroups = new Set([...state.selectedLeagueGroups].filter((key) => validLeagueGroupKeys.has(key)));
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
