"""Reproducible Playwright scraper for the Bahria University (E-8) CS faculty.

Pulls the live faculty roster and each faculty detail page from bahria.edu.pk,
extracts name / designation / email / research areas, and writes the normalised
result to ``scripts/scraped_roster.json``. ``build_seed.py`` then turns the
roster into the full ResearchSense dataset.

Setup (one time):
    pip install playwright && python -m playwright install chromium

Run:
    python -m scripts.scrape_bahria

Note: the faculty listing is a JS-rendered table; if the site markup changes,
adjust the selectors below. The committed roster in ``roster_data.py`` is a
captured snapshot so the app works without re-running this scraper.
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROSTER_URL = (
    "https://www.bahria.edu.pk/page/PageTemplate4?pageContentId=4687&WebsiteID=2"
)
DETAIL_URL = "https://www.bahria.edu.pk/Home/FacultyDetails?facultyId={id}"
OUTPUT = Path(__file__).resolve().parent / "scraped_roster.json"


def scrape_roster(page) -> list[dict]:
    """Extract (name, designation, faculty_id) rows from the roster table."""
    page.goto(ROSTER_URL, wait_until="networkidle")
    rows = page.locator("table tr")
    people: list[dict] = []
    for i in range(rows.count()):
        cells = rows.nth(i).locator("td")
        if cells.count() < 3:
            continue
        name = cells.nth(1).inner_text().strip()
        designation = cells.nth(2).inner_text().strip()
        link = cells.nth(1).locator("a")
        fid = None
        if link.count():
            href = link.first.get_attribute("href") or ""
            if "facultyId=" in href:
                fid = int(href.split("facultyId=")[1].split("&")[0])
        if name:
            people.append({"full_name": name, "designation": designation,
                           "faculty_id": fid})
    return people


def scrape_detail(page, faculty_id: int) -> dict:
    """Extract email and research areas from a faculty detail page."""
    page.goto(DETAIL_URL.format(id=faculty_id), wait_until="networkidle")
    detail: dict = {"email": None, "areas": ""}
    email = page.locator("a[href^='mailto:']")
    if email.count():
        detail["email"] = email.first.inner_text().strip()
    for i in range(page.locator("tr").count()):
        row = page.locator("tr").nth(i).inner_text()
        if "Research Areas" in row or "Expertise" in row:
            detail["areas"] = row.split("Expertise")[-1].strip()
            break
    return detail


def main() -> None:
    print("Scraping Bahria E-8 CS faculty...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        roster = scrape_roster(page)
        print(f"  roster: {len(roster)} faculty")
        for person in roster:
            if person["faculty_id"]:
                try:
                    person.update(scrape_detail(page, person["faculty_id"]))
                except Exception as exc:  # noqa: BLE001 - skip flaky detail pages
                    print(f"  ! detail {person['faculty_id']} failed: {exc}")
        browser.close()

    with OUTPUT.open("w", encoding="utf-8") as fh:
        json.dump(roster, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {OUTPUT} ({len(roster)} records).")
    print("Next: python -m scripts.build_seed")


if __name__ == "__main__":
    main()
