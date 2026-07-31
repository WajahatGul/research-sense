"""Re-apply fixed normalizers to already-generated researcher/project data.

This is an idempotent post-pass to fix names/departments in existing data
without re-running the multi-hour fetch. Called by Task 17 before index rebuild.
"""
import json
from pathlib import Path
from normalize import normalize_name, canonical_department

DATA_DIR = Path(__file__).parent.parent / "app" / "data"


def patch_normalized_names():
    """Patch researchers.json and projects.json with fixed normalizers."""
    researchers_path = DATA_DIR / "researchers.json"
    projects_path = DATA_DIR / "projects.json"

    with open(researchers_path) as f:
        researchers = json.load(f)

    with open(projects_path) as f:
        projects = json.load(f)

    patched = 0
    for researcher in researchers:
        old_name = researcher.get("full_name", "")
        old_dept = researcher.get("department", "")
        new_name = normalize_name(old_name)
        new_dept = canonical_department(old_dept)

        if new_name != old_name or new_dept != old_dept:
            patched += 1
            bio = researcher.get("profile_bio", "")
            if old_name and new_name != old_name:
                bio = bio.replace(old_name, new_name)
            if old_dept and new_dept != old_dept:
                bio = bio.replace(old_dept, new_dept)
            researcher["full_name"] = new_name
            researcher["department"] = new_dept
            researcher["profile_bio"] = bio

    for project in projects:
        pi_name = project.get("principal_investigator_name", "")
        pi_dept = project.get("department", "")
        new_pi_name = normalize_name(pi_name)
        new_pi_dept = canonical_department(pi_dept)
        if new_pi_name != pi_name:
            project["principal_investigator_name"] = new_pi_name
        if new_pi_dept != pi_dept:
            project["department"] = new_pi_dept

    with open(researchers_path, "w") as f:
        json.dump(researchers, f, indent=2)

    with open(projects_path, "w") as f:
        json.dump(projects, f, indent=2)

    print(f"Patched {patched} researcher records")


if __name__ == "__main__":
    patch_normalized_names()
