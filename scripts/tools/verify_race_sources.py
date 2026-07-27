#!/usr/bin/env python3
"""One-off verification run for candidate cycling races (NOT part of the
weekly update.yml pipeline -- run manually, roughly once a year before a new
season, e.g. `python scripts/tools/verify_race_sources.py`).

For every race in race_candidates.json, checks whether the current and next
year's Wikipedia article is scrapeable by scripts/fetch_cycling.py the same
way the existing races are -- and prints/writes a recommendation (scraper vs.
manual CSV entry) per race. Read-only: never touches config.json or
data/*.json. Transferring a recommendation into config.json stays a
deliberate, separate, human step.

All current candidates are stage races, so this only exercises the
stage-table path (fetch_stage_table_section_index + parse_stage_table), not
the one-day infobox-date path -- see README/the taxonomy prompt for why
one-day verification is a deferred follow-up.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_cycling
from common import load_config, log

CANDIDATES_PATH = Path(__file__).resolve().parent / "race_candidates.json"
REPORT_PATH = Path(__file__).resolve().parent / "verification-report.md"

# Names where the standard "{year} {name}" guess is unlikely to match the
# real Wikipedia title (sponsor prefixes/suffixes that change yearly, or
# likely name variants) -- flagged for a manual title lookup instead of
# risking a wrong guess that silently returns "article-missing".
TITLE_UNCLEAR = {
    "Tour de France Femmes avec Zwift",
    "Lloyds Tour of Britain Women",
    "Vuelta a Burgos Feminas",
}

STATUS_OK = "ok"
STATUS_ARTICLE_MISSING = "article-missing"
STATUS_UNPARSEABLE = "unparseable"
STATUS_TITLE_UNCLEAR = "title-unclear"


def load_candidates() -> list[dict]:
    with CANDIDATES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def guess_title(name: str, year: int) -> str | None:
    if name in TITLE_UNCLEAR:
        return None
    return f"{year} {name}"


def classify_title(api_base: str, title: str, year: int) -> str:
    """Assumes `title` is not None -- callers handle the title-unclear case
    themselves without a network call."""
    if not fetch_cycling.page_exists(api_base, title):
        return STATUS_ARTICLE_MISSING

    section_index = fetch_cycling.fetch_stage_table_section_index(api_base, title)
    if section_index is None:
        return STATUS_UNPARSEABLE
    section_wikitext = fetch_cycling.fetch_wikitext_section(api_base, title, section=section_index)
    if not section_wikitext:
        return STATUS_UNPARSEABLE
    stages = fetch_cycling.parse_stage_table(section_wikitext, year=year)
    if not stages:
        return STATUS_UNPARSEABLE
    return STATUS_OK


def verify_candidate(api_base: str, candidate: dict, years: list[int]) -> dict:
    results: dict[int, str] = {}
    for year in years:
        title = guess_title(candidate["name"], year)
        if title is None:
            results[year] = STATUS_TITLE_UNCLEAR
            continue
        try:
            results[year] = classify_title(api_base, title, year)
        except Exception as exc:  # a single race must not abort the whole batch
            results[year] = f"error: {exc}"
    recommendation = "Scraper" if all(r == STATUS_OK for r in results.values()) else "Manuell"
    return {**candidate, "results": results, "recommendation": recommendation}


def render_report(verified: list[dict], years: list[int]) -> str:
    header = ["Rennen", "Gender", *[str(y) for y in years], "Empfehlung"]
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * len(header)) + "|",
    ]
    for v in verified:
        row = [v["name"], v["gender"], *[v["results"][y] for y in years], v["recommendation"]]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main() -> None:
    config = load_config()
    api_base = config["cycling"]["wikipediaApi"]
    today = datetime.now(timezone.utc).date()
    years = [today.year, today.year + 1]

    candidates = load_candidates()
    verified = [verify_candidate(api_base, c, years) for c in candidates]

    report = render_report(verified, years)
    log(report)
    REPORT_PATH.write_text(report + "\n", encoding="utf-8")
    log(f"Report geschrieben nach {REPORT_PATH}")


if __name__ == "__main__":
    main()
