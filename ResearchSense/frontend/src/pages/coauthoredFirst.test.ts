import { describe, expect, it } from "vitest";

import type { PublicationRef } from "../types";
import { coauthoredFirst } from "./coauthoredFirst";

function pub(id: number, authorIds: number[]): PublicationRef {
  return {
    publication_id: id,
    title: `Paper ${id}`,
    publication_year: 2020,
    journal_name: "J",
    citation_count: 0,
    doi: null,
    author_ids: authorIds,
  };
}

describe("coauthoredFirst", () => {
  it("moves papers co-authored with both the profile and the origin researcher to the front", () => {
    const pubs = [pub(1, [10]), pub(2, [10, 20]), pub(3, [10]), pub(4, [10, 20])];
    const result = coauthoredFirst(pubs, 10, 20);
    expect(result.map((p) => p.publication_id)).toEqual([2, 4, 1, 3]);
  });

  it("preserves the original order within each group (stable)", () => {
    const pubs = [pub(1, [10, 20]), pub(2, [10, 20]), pub(3, [10])];
    const result = coauthoredFirst(pubs, 10, 20);
    expect(result.map((p) => p.publication_id)).toEqual([1, 2, 3]);
  });

  it("leaves order untouched when no with id is given", () => {
    const pubs = [pub(1, [10]), pub(2, [10, 20]), pub(3, [10])];
    const result = coauthoredFirst(pubs, 10, null);
    expect(result.map((p) => p.publication_id)).toEqual([1, 2, 3]);
  });

  it("leaves order untouched when the with id never co-authored anything", () => {
    const pubs = [pub(1, [10]), pub(2, [10, 30]), pub(3, [10])];
    const result = coauthoredFirst(pubs, 10, 999);
    expect(result.map((p) => p.publication_id)).toEqual([1, 2, 3]);
  });
});
