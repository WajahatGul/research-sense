Feature: Research discovery quality
  Suggestions, filters, and naming meet the supervisor's requirements.

  Scenario: Collaborator suggestions require a real signal and honor sorting
    Given a roster where only some researchers share areas or papers
    Then no suggestion lacks both a shared area and a co-authored paper
    And sorting by "name" returns suggestions in alphabetical order
    And the default order puts a past co-author first

  Scenario: Publications filter by period, department, and type
    Given publications from several departments, years, and types
    Then filtering years 2019-2020 for "Psychology" conference papers matches only such records

  Scenario: Researcher names carry no honorifics
    Given the seed name normalizer
    Then "Dr.Sana Aroos Khattak" is stored as "Sana Aroos Khattak"
    And "Prof Dr Saad Alvi" is stored as "Saad Alvi"
