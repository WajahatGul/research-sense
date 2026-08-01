from scripts.fetch_publications import clean_title


class TestCleanTitleMathML:
    def test_removes_mathml_block_entirely_without_welding_words(self):
        title = (
            "Viscous dissipation effects surrounded by "
            '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML" '
            'altimg="si2.svg"><mml:mrow><mml:mi>A</mml:mi></mml:mrow>'
            "</mml:math> nanofluid"
        )
        assert (
            clean_title(title) == "Viscous dissipation effects surrounded by nanofluid"
        )

    def test_mathml_only_title_falls_back_to_untitled(self):
        title = (
            '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML">'
            "<mml:mrow><mml:mi>A</mml:mi></mml:mrow></mml:math>"
        )
        assert clean_title(title) == "Untitled"


class TestCleanTitleInlineTags:
    def test_strips_sub_tags_without_inserting_spaces(self):
        title = (
            "Fe<sub>3</sub>O<sub>4</sub> and Al<sub>2</sub>O<sub>3</sub> nanoparticles"
        )
        assert clean_title(title) == "Fe3O4 and Al2O3 nanoparticles"

    def test_strips_italic_tags(self):
        assert clean_title("<i>E. coli</i>") == "E. coli"

    def test_strips_scp_tags(self):
        assert clean_title("<scp>G7</scp> economies") == "G7 economies"

    def test_strips_nested_italic_and_sub_tags(self):
        title = "<i>F</i><sub><i>p</i></sub> multipliers"
        assert clean_title(title) == "Fp multipliers"

    def test_strips_bold_em_strong_tags(self):
        title = "<b>Bold</b> <em>emph</em> <strong>strong</strong> word"
        assert clean_title(title) == "Bold emph strong word"

    def test_strips_unknown_tag(self):
        assert clean_title("A <foo>weird</foo> tag") == "A weird tag"


class TestCleanTitleEntities:
    def test_ampersand_entity_resolved(self):
        assert clean_title("Salt &amp; Pepper") == "Salt & Pepper"

    def test_double_escaped_ampersand_fully_resolved(self):
        assert clean_title("Salt &amp;amp; Pepper") == "Salt & Pepper"

    def test_numeric_entity_resolved(self):
        assert clean_title("It&#39;s a title") == "It's a title"


class TestCleanTitleOrdering:
    def test_escaped_tag_is_unescaped_then_stripped(self):
        # &lt;sub&gt; must become a real <sub> tag after unescaping, then be
        # stripped by the tag-removal step.
        assert clean_title("H&lt;sub&gt;2&lt;/sub&gt;O") == "H2O"


class TestCleanTitlePreservesExisting:
    def test_clean_title_passes_through_unchanged(self):
        assert clean_title("A perfectly normal title") == "A perfectly normal title"

    def test_latex_math_stripped(self):
        assert clean_title("Effects of $x^2$ on growth") == "Effects of on growth"

    def test_latex_command_stripped(self):
        assert clean_title(r"A study of \alpha decay") == "A study of decay"

    def test_stray_braces_stripped(self):
        assert clean_title("A {special} title") == "A special title"

    def test_empty_string_returns_untitled(self):
        assert clean_title("") == "Untitled"

    def test_none_returns_untitled(self):
        assert clean_title(None) == "Untitled"
