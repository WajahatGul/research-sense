"""Re-apply fixed normalizers to already-generated researcher/project data.

This is an idempotent post-pass to fix names/departments in existing data
without re-running the multi-hour fetch. Called by Task 17 before index rebuild.
"""

import json
import re
from pathlib import Path

try:
    from scripts.normalize import canonical_department, normalize_name
except ImportError:
    from normalize import canonical_department, normalize_name

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

    # Fix name honorifics
    new_name = normalize_name(old_name)
    if new_name != old_name:
        researcher["full_name"] = new_name
        bio = re.sub(rf"\b{re.escape(old_name)}\b", new_name, bio)
        changed = True

    if changed:
        researcher["profile_bio"] = bio
    return changed


def patch_normalized_names():
    """Patch researchers.json and projects.json with fixed normalizers."""
    scraped_path = Path(__file__).parent / "scraped_faculty.json"
    researchers_path = DATA_DIR / "researchers.json"
    projects_path = DATA_DIR / "projects.json"

    with open(scraped_path) as f:
        scraped = json.load(f)
    dept_fixes = department_fixes(scraped)

    with open(researchers_path) as f:
        researchers = json.load(f)

    with open(projects_path) as f:
        projects = json.load(f)

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

    with open(researchers_path, "w") as f:
        json.dump(researchers, f, indent=2)

    with open(projects_path, "w") as f:
        json.dump(projects, f, indent=2)

    print(f"Patched {patched} researcher records")


if __name__ == "__main__":
    patch_normalized_names()
