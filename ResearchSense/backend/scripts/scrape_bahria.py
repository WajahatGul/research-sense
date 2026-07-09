"""Headless Playwright scraper for Bahria University computing faculty.

Source: the university faculty directory at bahria.edu.pk/Home/Faculty, a single
searchable table covering every campus with name, campus, department,
designation, and research areas. This script pulls the computing departments
(Computer Science, Software Engineering, Computer Engineering) across the four
teaching campuses and then visits each faculty detail page for the real email
and qualification.

Publications are not published on the site, so they are not scraped here;
fetch_publications.py adds real publications from OpenAlex.

Setup (one time):
    pip install playwright && python -m playwright install chromium

Run (from backend/):
    python -m scripts.scrape_bahria

Output: scripts/scraped_faculty.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

FACULTY_URL = "https://www.bahria.edu.pk/Home/Faculty"
DETAIL_URL = "https://www.bahria.edu.pk/Home/FacultyDetails?facultyId={id}"
OUTPUT = Path(__file__).resolve().parent / "scraped_faculty.json"

# Campus codes in the directory mapped to display names (four teaching campuses).
DIRECTORY_JS = """
() => {
  const $ = window.jQuery || window.$;
  const table = document.querySelector('table');
  const nodes = $(table).DataTable().rows().nodes().toArray();
  const CAMPUS = { BUIC_E8:'Islamabad (E-8)', BUIC_H11:'Islamabad (H-11)',
                   BUKC:'Karachi', BUKC_IPP:'Karachi', BULC:'Lahore' };
  const computing = /computer science|software engineering|computer engineering/i;
  const out = [];
  for (const tr of nodes) {
    const c = [...tr.querySelectorAll('td')].map(x => x.innerText.trim().replace(/\\s+/g,' '));
    const a = tr.querySelector('a[href*="facultyId="]');
    const id = a ? a.getAttribute('href').split('facultyId=')[1].split('&')[0] : null;
    const [name, code, dept, designation, areas] = c;
    if (!CAMPUS[code] || !computing.test(dept || '')) continue;
    out.push({ id, name, campus: CAMPUS[code],
               department: /software/i.test(dept) ? 'Software Engineering'
                 : /computer engineering/i.test(dept) ? 'Computer Engineering'
                 : 'Computer Science',
               designation, areas: areas || '' });
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
    detail_areas: areasRow ? areasRow.slice(1).join(' ').trim() : '',
    degree: qual ? qual[0] : null,
    degree_year: qual ? qual[1] : null,
    degree_majors: qual ? qual[2] : null,
    degree_university: qual ? qual[3] : null,
  };
}
"""

READY = ("() => { const $=window.jQuery; const t=document.querySelector('table'); "
         "return $ && t && $(t).DataTable().rows().count() > 100; }")


def main() -> None:
    print("Scraping Bahria computing faculty from the directory...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FACULTY_URL, wait_until="networkidle", timeout=90000)
        page.wait_for_function(READY, timeout=60000)
        roster = page.evaluate(DIRECTORY_JS)
        print(f"  directory: {len(roster)} computing faculty across 4 campuses")

        for i, person in enumerate(roster, start=1):
            if not person["id"]:
                continue
            try:
                page.goto(DETAIL_URL.format(id=person["id"]),
                          wait_until="domcontentloaded", timeout=60000)
                d = page.evaluate(DETAIL_JS)
                person["email"] = d.get("email")
                # Directory areas are primary; detail areas are a fallback.
                if not person["areas"] and d.get("detail_areas"):
                    person["areas"] = d["detail_areas"]
                for k in ("degree", "degree_year", "degree_majors", "degree_university"):
                    person[k] = d.get(k)
                if i % 25 == 0:
                    print(f"    detail {i}/{len(roster)}")
            except Exception as exc:  # noqa: BLE001 - keep going on flaky pages
                print(f"    detail {person['name'][:24]} failed: {exc}")
            time.sleep(0.1)
        browser.close()

    OUTPUT.write_text(json.dumps(roster, indent=2, ensure_ascii=False), "utf-8")
    with_email = sum(1 for p in roster if p.get("email"))
    with_areas = sum(1 for p in roster if p.get("areas"))
    print(f"Wrote {OUTPUT}: {len(roster)} faculty, "
          f"{with_email} with email, {with_areas} with research areas.")
    print("Next: python -m scripts.build_seed && python -m scripts.fetch_publications")


if __name__ == "__main__":
    main()
