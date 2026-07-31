from scripts.fetch_publications import classify_publication_type


class TestClassifyPublicationType:
    def test_proceedings_article_type_is_conference(self):
        assert (
            classify_publication_type("proceedings-article", "Some Random Venue")
            == "conference"
        )

    def test_venue_with_conference_keyword_is_conference(self):
        assert (
            classify_publication_type(
                None, "2021 International Bhurban Conference on Applied Sciences"
            )
            == "conference"
        )

    def test_venue_with_conference_word_in_title_is_conference(self):
        assert (
            classify_publication_type(None, "2017 Computing Conference") == "conference"
        )

    def test_proceedings_without_conference_keyword_but_with_journal_stays_journal(
        self,
    ):
        # Real example: contains "Proceedings" but is actually a journal
        assert (
            classify_publication_type(
                None,
                "Proceedings of the Institution of Mechanical Engineers Part E "
                "Journal of Process Mechanical Engineering",
            )
            == "journal"
        )

    def test_plain_journal_name_is_journal(self):
        assert (
            classify_publication_type(None, "IEEE Transactions on Neural Networks")
            == "journal"
        )

    def test_empty_venue_is_journal(self):
        assert classify_publication_type(None, "") == "journal"
