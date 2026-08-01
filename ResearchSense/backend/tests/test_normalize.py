from scripts.normalize import (
    academic_rank,
    canonical_department,
    normalize_name,
    split_expertise,
    title_case_name,
)


class TestNormalizeName:
    def test_strips_dr_prefix(self):
        assert normalize_name("Dr Arshad Farhad") == "Arshad Farhad"

    def test_strips_dotted_title(self):
        assert normalize_name("Dr. Moneeb Gohar") == "Moneeb Gohar"

    def test_strips_stacked_titles(self):
        assert normalize_name("Prof Dr Saad Alvi") == "Saad Alvi"

    def test_strips_engr(self):
        assert normalize_name("Engr. Junaid Nasir") == "Junaid Nasir"

    def test_plain_name_untouched(self):
        assert normalize_name("Abdul Raheem Aleem") == "Abdul Raheem Aleem"

    def test_name_starting_with_titlelike_token_kept(self):
        # "Misbah" starts with "Mis…" but is a real name, not "Miss ..."
        assert normalize_name("Misbah Khan") == "Misbah Khan"

    def test_whitespace_collapsed(self):
        assert normalize_name("  Dr   Ali   Raza ") == "Ali Raza"

    def test_strips_dotted_title_without_space(self):
        # FINDING 1: dotted honorific without trailing space
        assert normalize_name("Dr.Sana Aroos Khattak") == "Sana Aroos Khattak"

    def test_strips_stacked_dotted_titles(self):
        # FINDING 1: stacked dotted honorifics
        assert normalize_name("Prof.Dr.Ali Raza") == "Ali Raza"

    def test_name_starting_with_dr_word(self):
        # FINDING 1: "Drew" starts with "dr" but is a real name, not a title
        assert normalize_name("Drew Smith") == "Drew Smith"

    def test_strips_spelled_out_engineer(self):
        # FINDING 1: live data contains "Engineer Muhammad Saim"; "Engineer"
        # must be stripped, not just the abbreviated "Engr"
        assert normalize_name("Engineer Muhammad Saim") == "Muhammad Saim"

    def test_strips_engr_still_works(self):
        # FINDING 1: adding "engineer" to the alternation must not shadow
        # or break the existing abbreviated "Engr." form
        assert normalize_name("Engr. Ali Raza") == "Ali Raza"

    def test_name_starting_with_engineer_like_token_kept(self):
        # "Engrid" starts with the literal "Engr" title text but is a real
        # name, not a title (mirrors test_name_starting_with_dr_word above)
        assert normalize_name("Engrid Larsen") == "Engrid Larsen"


class TestCanonicalDepartment:
    def test_title_case_and_trim(self):
        assert canonical_department(" computer science ") == "Computer Science"

    def test_department_of_prefix_removed(self):
        assert canonical_department("Department of Psychology") == "Psychology"

    def test_ampersand_normalized(self):
        assert (
            canonical_department("Humanities & Social Sciences")
            == "Humanities and Social Sciences"
        )

    def test_empty_becomes_general(self):
        assert canonical_department("") == "General"

    def test_preserves_all_caps_acronyms(self):
        # FINDING 2: preserve fully-uppercase words (len >= 2)
        assert canonical_department("HR & Management") == "HR and Management"

    def test_preserves_ipp_acronym(self):
        # FINDING 2: single fully-uppercase word should stay uppercase
        assert canonical_department("IPP") == "IPP"

    def test_repairs_mangled_hr_from_scraper(self):
        # ROUND 3: scraper already mangles to "Hr and Management", must repair
        assert canonical_department("Hr and Management") == "HR and Management"

    def test_repairs_mangled_ipp_from_scraper(self):
        # ROUND 3: scraper already mangles to "Ipp", must repair
        assert canonical_department("ipp") == "IPP"

    def test_raw_case_preserved_with_acronym(self):
        # ROUND 3: verify "HR & Management" still works (raw all-caps)
        assert canonical_department("HR & Management") == "HR and Management"


class TestAcademicRank:
    def test_compound_hod_role(self):
        assert (
            academic_rank("Associate Professor / HoD HR & Management")
            == "Associate Professor"
        )

    def test_senior_assistant_professor_program_manager(self):
        assert (
            academic_rank("Senior Assistant Professor/ Program Manager")
            == "Senior Assistant Professor"
        )

    def test_dean_and_principal_role(self):
        assert academic_rank("Dean & Principal / Associate Professor") == (
            "Associate Professor"
        )

    def test_professor_of_law(self):
        assert academic_rank("Professor of Law") == "Professor"

    def test_senior_professor_hod(self):
        assert (
            academic_rank("Senior Professor / HoD Media Studies") == "Senior Professor"
        )

    def test_no_rank_found_returns_other(self):
        assert academic_rank("Departmental Coordinator") == "Other"

    def test_head_of_department_returns_other(self):
        assert academic_rank("Head of Department") == "Other"

    def test_empty_returns_other(self):
        assert academic_rank("") == "Other"

    def test_none_returns_other(self):
        assert academic_rank(None) == "Other"

    def test_senior_assistant_professor_does_not_collapse_to_assistant(self):
        rank = academic_rank("Senior Assistant Professor")
        assert rank == "Senior Assistant Professor"
        assert rank != "Assistant Professor"
        assert rank != "Professor"

    def test_senior_associate_professor_does_not_collapse(self):
        rank = academic_rank("Senior Associate Professor")
        assert rank == "Senior Associate Professor"
        assert rank != "Associate Professor"
        assert rank != "Professor"

    def test_senior_lecturer_does_not_collapse_to_lecturer(self):
        rank = academic_rank("Senior Lecturer")
        assert rank == "Senior Lecturer"
        assert rank != "Lecturer"

    def test_plain_lecturer(self):
        assert academic_rank("Lecturer") == "Lecturer"

    def test_case_insensitive(self):
        assert (
            academic_rank("senior assistant professor") == "Senior Assistant Professor"
        )


class TestTitleCaseName:
    def test_all_caps_converted(self):
        assert title_case_name("ASIF MASOOD") == "Asif Masood"

    def test_mixed_case_untouched(self):
        assert title_case_name("Muhammad Arif Khattak") == "Muhammad Arif Khattak"

    def test_empty_string(self):
        assert title_case_name("") == ""

    def test_mixed_case_with_acronym_untouched(self):
        assert title_case_name("Ali Khan (IT)") == "Ali Khan (IT)"

    def test_other_allcaps_examples(self):
        assert title_case_name("GHULAM MUHAMMAD") == "Ghulam Muhammad"
        assert title_case_name("MUHAMMAD SADIQ KAKAR") == "Muhammad Sadiq Kakar"
        assert title_case_name("KHAWER BILAL") == "Khawer Bilal"


class TestSplitExpertise:
    def test_splits_on_commas_and_semicolons(self):
        assert split_expertise("Machine Learning, NLP; Data Mining") == [
            "Machine Learning",
            "Natural Language Processing",
            "Data Mining",
        ]

    def test_canonicalizes_variants(self):
        assert split_expertise("AI and ML") == [
            "Artificial Intelligence",
            "Machine Learning",
        ]

    def test_dedupes_case_variants(self):
        assert split_expertise("deep learning, Deep Learning") == ["Deep Learning"]

    def test_empty_gives_empty_list(self):
        assert split_expertise("") == []
