from scripts.patch_normalized_names import (
    department_fixes,
    patch_project,
    patch_publication,
    patch_publication_title,
    patch_researcher,
)


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

    def test_fixes_all_caps_name(self):
        dept_fixes = {}
        researcher = {
            "full_name": "ASIF MASOOD",
            "department": "Computer Science",
            "profile_bio": "ASIF MASOOD is a lecturer.",
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is True
        assert researcher["full_name"] == "Asif Masood"
        assert researcher["profile_bio"] == "Asif Masood is a lecturer."

    def test_sets_academic_rank_from_designation(self):
        dept_fixes = {}
        researcher = {
            "full_name": "Ali Khan",
            "department": "Psychology",
            "designation": "Associate Professor / HoD HR & Management",
            "profile_bio": "Works in Psychology",
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is True
        assert researcher["academic_rank"] == "Associate Professor"

    def test_refreshes_stale_academic_rank(self):
        dept_fixes = {}
        researcher = {
            "full_name": "Ali Khan",
            "department": "Psychology",
            "designation": "Senior Assistant Professor",
            "academic_rank": "Assistant Professor",
            "profile_bio": "Works in Psychology",
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is True
        assert researcher["academic_rank"] == "Senior Assistant Professor"

    def test_academic_rank_already_correct_no_change(self):
        dept_fixes = {"psychology": "Psychology"}
        researcher = {
            "full_name": "Ali Khan",
            "department": "Psychology",
            "designation": "Lecturer",
            "academic_rank": "Lecturer",
            "profile_bio": "Works in Psychology",
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is False

    def test_no_designation_key_skips_academic_rank(self):
        # Synthetic/older records without a designation field are left alone.
        dept_fixes = {}
        researcher = {
            "full_name": "Ali Khan",
            "department": "Psychology",
            "profile_bio": "Works in Psychology",
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is False
        assert "academic_rank" not in researcher

    def test_fixes_spelled_out_engineer_honorific(self):
        # FINDING 1: the researcher pass must also catch "Engineer" (not
        # just the abbreviated "Engr"), e.g. live data's "Engineer Muhammad
        # Saim"
        dept_fixes = {}
        researcher = {
            "full_name": "Engineer Muhammad Saim",
            "department": "Software Engineering",
            "profile_bio": "Engineer Muhammad Saim researches software.",
        }
        changed = patch_researcher(researcher, dept_fixes)
        assert changed is True
        assert researcher["full_name"] == "Muhammad Saim"
        assert researcher["profile_bio"] == "Muhammad Saim researches software."


class TestPatchProject:
    def test_removes_funding_and_date_fields(self):
        project = {
            "project_id": 1,
            "project_title": "AI for Healthcare",
            "description": "A funded research project applying ai to healthcare "
            "challenges in Pakistan.",
            "start_date": "2021-03-01",
            "end_date": "2023-12-31",
            "status": "ongoing",
            "funding": [
                {
                    "funding_id": 1,
                    "agency_name": "HEC",
                    "country": "Pakistan",
                    "amount": 5000000.0,
                    "currency": "PKR",
                }
            ],
        }
        changed = patch_project(project)
        assert changed is True
        assert "funding" not in project
        assert "start_date" not in project
        assert "end_date" not in project
        assert "status" not in project

    def test_rewrites_funded_description(self):
        project = {
            "project_id": 1,
            "description": "A funded research project applying ai to healthcare "
            "challenges in Pakistan.",
        }
        changed = patch_project(project)
        assert changed is True
        assert project["description"] == (
            "An illustrative research direction in ai for the healthcare domain."
        )
        assert "funded" not in project["description"]
        assert "grant" not in project["description"].lower()

    def test_no_change_when_already_patched(self):
        project = {
            "project_id": 1,
            "description": "An illustrative research direction in ai for the "
            "healthcare domain.",
        }
        changed = patch_project(project)
        assert changed is False

    def test_idempotent_second_pass_no_change(self):
        project = {
            "project_id": 1,
            "description": "A funded research project applying ai to healthcare "
            "challenges in Pakistan.",
            "start_date": "2021-03-01",
            "status": "ongoing",
            "funding": [],
        }
        first = patch_project(project)
        second = patch_project(project)
        assert first is True
        assert second is False

    def test_missing_optional_fields_is_a_no_op_for_those_keys(self):
        project = {"project_id": 1, "description": "Already fine."}
        changed = patch_project(project)
        assert changed is False
        assert "funding" not in project
        assert "start_date" not in project


class TestPatchPublication:
    def test_reclassifies_conference_venue_missed_by_openalex_type(self):
        # FINDING 2: OpenAlex's `type` field almost never says
        # "proceedings-article" in our data, so the venue-name fallback must
        # requalify a publication_type of "journal" -> "conference".
        pub = {
            "journal_name": "2021 International Bhurban Conference on Applied Sciences",
            "publication_type": "journal",
        }
        changed = patch_publication(pub)
        assert changed is True
        assert pub["publication_type"] == "conference"

    def test_keeps_proceedings_journal_as_journal(self):
        # Real example: contains "Proceedings" but is genuinely a journal.
        pub = {
            "journal_name": (
                "Proceedings of the Institution of Mechanical Engineers Part E "
                "Journal of Process Mechanical Engineering"
            ),
            "publication_type": "journal",
        }
        changed = patch_publication(pub)
        assert changed is False
        assert pub["publication_type"] == "journal"

    def test_no_change_when_already_correct(self):
        pub = {
            "journal_name": "IEEE Transactions on Neural Networks",
            "publication_type": "journal",
        }
        changed = patch_publication(pub)
        assert changed is False

    def test_handles_missing_journal_name(self):
        pub = {"publication_type": "journal"}
        changed = patch_publication(pub)
        assert changed is False
        assert pub["publication_type"] == "journal"


class TestPatchPublicationTitle:
    def test_strips_mathml_block(self):
        pub = {
            "title": (
                "Viscous dissipation effects surrounded by "
                '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML" '
                'altimg="si2.svg"><mml:mrow><mml:mi>A</mml:mi></mml:mrow>'
                "</mml:math> nanofluid"
            )
        }
        changed = patch_publication_title(pub)
        assert changed is True
        assert pub["title"] == "Viscous dissipation effects surrounded by nanofluid"

    def test_strips_inline_tags_without_inserting_spaces(self):
        pub = {"title": "Fe<sub>3</sub>O<sub>4</sub> nanoparticles"}
        changed = patch_publication_title(pub)
        assert changed is True
        assert pub["title"] == "Fe3O4 nanoparticles"

    def test_resolves_double_escaped_entity(self):
        pub = {"title": "Salt &amp;amp; Pepper"}
        changed = patch_publication_title(pub)
        assert changed is True
        assert pub["title"] == "Salt & Pepper"

    def test_no_change_when_already_clean(self):
        pub = {"title": "A perfectly normal title"}
        changed = patch_publication_title(pub)
        assert changed is False
        assert pub["title"] == "A perfectly normal title"

    def test_missing_title_key_is_a_no_op(self):
        pub = {"publication_type": "journal"}
        changed = patch_publication_title(pub)
        assert changed is False
        assert "title" not in pub

    def test_idempotent_second_pass_no_change(self):
        pub = {"title": "<i>E. coli</i> &amp; friends"}
        first = patch_publication_title(pub)
        second = patch_publication_title(pub)
        assert first is True
        assert second is False
        assert pub["title"] == "E. coli & friends"
