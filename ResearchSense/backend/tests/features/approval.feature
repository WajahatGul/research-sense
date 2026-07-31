Feature: Admin approval workflow for faculty papers
  Faculty submissions stay hidden until an admin approves them.

  Scenario: Submitted paper is pending and not published
    Given a faculty submission titled "Fog Computing Survey"
    Then the submission status is "pending"
    And the pending queue lists "Fog Computing Survey"
    And nothing has been published

  Scenario: Approval publishes the paper and merges its staged chunks
    Given a faculty submission titled "Fog Computing Survey"
    When an admin approves the submission
    Then the submission status is "approved"
    And the record was published
    And the staged chunks were merged

  Scenario: Rejection hides the paper and records the note
    Given a faculty submission titled "Fog Computing Survey"
    When an admin rejects the submission with note "duplicate of DOI 10.1/x"
    Then the submission status is "rejected"
    And the staged chunks were discarded
    And the faculty member can read the note "duplicate of DOI 10.1/x"
