"""Re-apply fixed normalizers to already-generated researcher/project data.

This is an idempotent post-pass to fix names/departments in existing data
without re-running the multi-hour fetch. Called by Task 17 before index rebuild.
"""

import json
import re
from pathlib import Path

try:
    from scripts.fetch_publications import classify_publication_type, clean_title
    from scripts.normalize import (
        academic_rank,
        canonical_department,
        normalize_name,
        title_case_name,
    )
except ImportError:
    from fetch_publications import classify_publication_type, clean_title
    from normalize import (
        academic_rank,
        canonical_department,
        normalize_name,
        title_case_name,
    )

DATA_DIR = Path(__file__).parent.parent / "app" / "data"


def department_fixes(scraped: list[dict]) -> dict[str, str]:
    """Build mapping from lowercased canonical output to corrected output.

    Recovers correct casing for departments that were lowercased in persisted
    data by using the scraped data (which has original casing).
    Returns {lowercased_output: corrected_output} for all unique departments.
    """
    fixes = {}
    for rec in scraped:
        raw_dept = rec.get("department", "")
        if raw_dept:
            fixed = canonical_department(raw_dept)
            fixes[fixed.lower()] = fixed
    return fixes


def patch_researcher(researcher: dict, dept_fixes: dict[str, str]) -> bool:
    """Patch a single researcher record. Returns True if any changes made."""
    old_name = researcher.get("full_name", "")
    old_dept = researcher.get("department", "")
    bio = researcher.get("profile_bio", "") or ""
    changed = False

    # Fix department casing from scraped mapping
    if old_dept:
        fixed_dept = dept_fixes.get(old_dept.lower())
        if fixed_dept and fixed_dept != old_dept:
            researcher["department"] = fixed_dept
            bio = re.sub(rf"\b{re.escape(old_dept)}\b", fixed_dept, bio)
            changed = True
            old_dept = fixed_dept

    # Fix name honorifics, then fix ALL-CAPS names to title case.
    new_name = title_case_name(normalize_name(old_name))
    if new_name != old_name:
        researcher["full_name"] = new_name
        bio = re.sub(rf"\b{re.escape(old_name)}\b", new_name, bio)
        changed = True

    # Refresh the academic rank derived from the designation, when present
    # (older/synthetic records without a designation field are untouched).
    if "designation" in researcher:
        new_rank = academic_rank(researcher.get("designation", ""))
        if researcher.get("academic_rank") != new_rank:
            researcher["academic_rank"] = new_rank
            changed = True

    if changed:
        researcher["profile_bio"] = bio
    return changed


def patch_publication(publication: dict) -> bool:
    """Recompute a single publication's type from its venue name.

    Uses classify_publication_type(None, journal_name) since the persisted
    data has no reliable OpenAlex `type` field to fall back on -- the venue
    name heuristic is the only signal available post-hoc. Returns True if
    publication_type changed.
    """
    old_type = publication.get("publication_type")
    new_type = classify_publication_type(None, publication.get("journal_name") or "")
    if new_type != old_type:
        publication["publication_type"] = new_type
        return True
    return False


def patch_publication_title(publication: dict) -> bool:
    """Re-apply clean_title to a single publication's title.

    Removes markup contamination (MathML blocks, inline formatting tags,
    escaped HTML entities) that leaked in from publisher metadata. A missing
    "title" key is a no-op (older/synthetic records). Returns True if the
    title changed, so a second pass over already-clean data is a no-op
    (idempotent).
    """
    old_title = publication.get("title")
    if old_title is None:
        return False
    new_title = clean_title(old_title)
    if new_title != old_title:
        publication["title"] = new_title
        return True
    return False


def patch_normalized_names():
    """Patch researchers.json, projects.json, and publications.json with
    fixed normalizers/classifiers."""
    scraped_path = Path(__file__).parent / "scraped_faculty.json"
    researchers_path = DATA_DIR / "researchers.json"
    projects_path = DATA_DIR / "projects.json"
    publications_path = DATA_DIR / "publications.json"

    with open(scraped_path, encoding="utf-8") as f:
        scraped = json.load(f)
    dept_fixes = department_fixes(scraped)

    with open(researchers_path, encoding="utf-8") as f:
        researchers = json.load(f)

    with open(projects_path, encoding="utf-8") as f:
        projects = json.load(f)

    with open(publications_path, encoding="utf-8") as f:
        publications = json.load(f)

    patched = 0
    for researcher in researchers:
        if patch_researcher(researcher, dept_fixes):
            patched += 1

    # Apply department casing fixes to projects
    for project in projects:
        dept = (project.get("department") or "").lower()
        if dept:
            fixed = dept_fixes.get(dept)
            if fixed and fixed != project["department"]:
                project["department"] = fixed

    pub_patched = 0
    title_patched = 0
    for publication in publications:
        if patch_publication(publication):
            pub_patched += 1
        if patch_publication_title(publication):
            title_patched += 1

    # researchers.json and projects.json are also written elsewhere with
    # ensure_ascii=False -- match that convention everywhere so this patch
    # doesn't rewrite every non-ASCII character as a \uXXXX escape.
    with open(researchers_path, "w", encoding="utf-8") as f:
        json.dump(researchers, f, indent=2, ensure_ascii=False)

    with open(projects_path, "w", encoding="utf-8") as f:
        json.dump(projects, f, indent=2, ensure_ascii=False)

    with open(publications_path, "w", encoding="utf-8") as f:
        json.dump(publications, f, indent=2, ensure_ascii=False)

    print(f"Patched {patched} researcher records")
    print(f"Patched {pub_patched} publication records")
    print(f"Patched {title_patched} publication titles")


if __name__ == "__main__":
    patch_normalized_names()
