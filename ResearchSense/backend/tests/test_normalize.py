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


class TestCanonicalDepartment:
    def test_title_case_and_trim(self):
        assert canonical_department(" computer science ") == "Computer Science"

    def test_department_of_prefix_removed(self):
        assert canonical_department("Department of Psychology") == "Psychology"

    def test_ampersand_normalized(self):
        assert canonical_department("Humanities & Social Sciences") == \
            "Humanities and Social Sciences"

    def test_empty_becomes_general(self):
        assert canonical_department("") == "General"


class TestSplitExpertise:
    def test_splits_on_commas_and_semicolons(self):
        assert split_expertise("Machine Learning, NLP; Data Mining") == \
            ["Machine Learning", "Natural Language Processing", "Data Mining"]

    def test_canonicalizes_variants(self):
        assert split_expertise("AI and ML") == \
            ["Artificial Intelligence", "Machine Learning"]

    def test_dedupes_case_variants(self):
        assert split_expertise("deep learning, Deep Learning") == ["Deep Learning"]

    def test_empty_gives_empty_list(self):
        assert split_expertise("") == []
