from scripts.normalize import canonical_department, normalize_name, split_expertise


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
