from scripts.patch_normalized_names import department_fixes, patch_researcher


class TestDepartmentFixes:
    def test_builds_mapping_from_scraped(self):
        scraped = [
            {"department": "HR & Management"},
            {"department": "IPP"},
        ]
        fixes = department_fixes(scraped)
        assert fixes["hr and management"] == "HR and Management"
        assert fixes["ipp"] == "IPP"

    def test_ignores_empty_departments(self):
        scraped = [
            {"department": ""},
            {"department": None},
        ]
        fixes = department_fixes(scraped)
        assert len(fixes) == 0

    def test_last_entry_wins_on_lowercase_collision(self):
        scraped = [
            {"department": "HR & Management"},
            {
                "department": "Hr & Management"
            },  # Both canonicalize with acronym allowlist
        ]
        fixes = department_fixes(scraped)
        # Both canonicalize to "HR and Management" with the acronym allowlist
        assert len(fixes) == 1
        assert fixes["hr and management"] == "HR and Management"

    def test_repairs_already_mangled_scraped_input(self):
        # The scraper already mangles "HR & Management" to "Hr and Management"
        # When we re-canonicalize with the acronym allowlist, we can recover it
        scraped = [
            {"department": "Hr and Management"},  # Already mangled by scraper
            {"department": "Ipp"},  # Already mangled
        ]
        fixes = department_fixes(scraped)
        # Now with the acronym allowlist in canonical_department, these repair
        assert fixes["hr and management"] == "HR and Management"
        assert fixes["ipp"] == "IPP"


class TestPatchResearcher:
    def test_fixes_department_casing(self):
        dept_fixes = {"hr and management": "HR and Management"}
        researcher = {
            "full_name": "Ali Khan",
            "department": "Hr and Management",
            "profile_bio": "Works in Hr and Management",
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is True
        assert researcher["department"] == "HR and Management"
        assert researcher["profile_bio"] == "Works in HR and Management"

    def test_fixes_name_honorifics(self):
        dept_fixes = {}
        researcher = {
            "full_name": "Dr. Sana Khan",
            "department": "Psychology",
            "profile_bio": "Dr. Sana Khan is a professor",
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is True
        assert researcher["full_name"] == "Sana Khan"
        assert researcher["profile_bio"] == "Sana Khan is a professor"

    def test_no_change_when_already_correct(self):
        dept_fixes = {"psychology": "Psychology"}
        researcher = {
            "full_name": "Ali Khan",
            "department": "Psychology",
            "profile_bio": "Works in Psychology",
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is False

    def test_word_boundary_safety_in_bio(self):
        dept_fixes = {}
        researcher = {
            "full_name": "Dr. Ali Khan",
            "department": "IT",
            "profile_bio": "Dr. Ali Khan works throughout the IT department",
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is True
        # "Dr. Ali Khan" should be replaced, but "throughout" should be untouched
        assert (
            researcher["profile_bio"] == "Ali Khan works throughout the IT department"
        )

    def test_both_name_and_department_fixed(self):
        dept_fixes = {"it": "IT"}
        researcher = {
            "full_name": "Prof. Dr. Sarah",
            "department": "it",
            "profile_bio": "Prof. Dr. Sarah leads it initiatives",
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is True
        assert researcher["full_name"] == "Sarah"
        assert researcher["department"] == "IT"
        assert researcher["profile_bio"] == "Sarah leads IT initiatives"

    def test_handles_none_profile_bio(self):
        dept_fixes = {}
        researcher = {
            "full_name": "Dr. Ali",
            "department": "Math",
            "profile_bio": None,
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is True
        assert researcher["full_name"] == "Ali"
        assert researcher["profile_bio"] == ""
