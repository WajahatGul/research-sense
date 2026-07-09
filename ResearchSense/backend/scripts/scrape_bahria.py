"""Headless Playwright scraper for the Bahria University (E-8) CS faculty.

Pulls the live faculty roster and every faculty detail page from bahria.edu.pk
and extracts the genuinely published fields: email, research areas / expertise,
and highest qualification (degree, year, majors, university). Publications and
funding are NOT published on the site, so they are not scraped; ``build_seed``
adds those as clearly flagged sample data.

Setup (one time):
    pip install playwright && python -m playwright install chromium

Run (from backend/):
    python -m scripts.scrape_bahria

Output: scripts/scraped_faculty.json
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROSTER_URL = (
    "https://www.bahria.edu.pk/page/PageTemplate4?pageContentId=4687&WebsiteID=2"
)
DETAIL_URL = "https://www.bahria.edu.pk/Home/FacultyDetails?facultyId={id}"
OUTPUT = Path(__file__).resolve().parent / "scraped_faculty.json"

ROSTER_JS = """
() => {
  const seen = new Set(); const out = [];
  for (const a of document.querySelectorAll('a[href*="facultyId="]')) {
    const id = a.getAttribute('href').split('facultyId=')[1].split('&')[0];
    if (seen.has(id)) continue; seen.add(id);
    const row = a.closest('tr');
    const cells = row ? [...row.querySelectorAll('td')].map(c => c.innerText.trim()) : [];
    out.push({ id, name: a.innerText.trim().replace(/\\s+/g,' '),
               designation: (cells[2] || '').replace(/\\s+/g,' ') });
  }
  return out;
}
"""

DETAIL_JS = """
() => {
  const rows = [...document.querySelectorAll('tr')].map(r =>
    [...r.querySelectorAll('td,th')].map(c => c.innerText.trim().replace(/\\s+/g,' ')));
  const find = (label) => rows.find(c => c[0] && c[0].toLowerCase().includes(label));
  const mail = document.querySelector('a[href^="mailto:"]');
  const areasRow = find('research areas');
  const degrees = ['phd','ph.d','ms','m.phil','mphil','msc','m.sc'];
  const qual = rows.find(c => degrees.includes((c[0] || '').toLowerCase()));
  return {
    email: mail ? mail.innerText.trim() : null,
    areas: areasRow ? areasRow.slice(1).join(' ').trim() : '',
    degree: qual ? qual[0] : null,
    degree_year: qual ? qual[1] : null,
    degree_majors: qual ? qual[2] : null,
    degree_university: qual ? qual[3] : null,
  };
}
"""


def main() -> None:
    print("Scraping Bahria E-8 CS faculty (headless)...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(ROSTER_URL, wait_until="domcontentloaded", timeout=60000)
        roster = page.evaluate(ROSTER_JS)
        print(f"  roster: {len(roster)} faculty with detail pages")

        for i, person in enumerate(roster, start=1):
            try:
                page.goto(DETAIL_URL.format(id=person["id"]),
                          wait_until="domcontentloaded", timeout=60000)
                person.update(page.evaluate(DETAIL_JS))
                mark = "ok" if person.get("email") else "no email"
                print(f"  [{i:>2}/{len(roster)}] {person['name'][:30]:30} {mark}")
            except Exception as exc:  # noqa: BLE001 - keep going on flaky pages
                print(f"  [{i:>2}/{len(roster)}] {person['name'][:30]:30} FAILED: {exc}")
        browser.close()

    with OUTPUT.open("w", encoding="utf-8") as fh:
        json.dump(roster, fh, indent=2, ensure_ascii=False)
    with_email = sum(1 for p in roster if p.get("email"))
    with_areas = sum(1 for p in roster if p.get("areas"))
    print(f"Wrote {OUTPUT}: {len(roster)} faculty, "
          f"{with_email} with email, {with_areas} with research areas.")
    print("Next: python -m scripts.build_seed")


if __name__ == "__main__":
    main()
