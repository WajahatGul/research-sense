import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/client";
import { fetchPublication, fetchRelatedPublications } from "../api/publications";
import type { Publication } from "../types";
import PublicationDetail from "./PublicationDetail";

vi.mock("../api/publications", () => ({
  fetchPublication: vi.fn(),
  fetchRelatedPublications: vi.fn(),
}));
vi.mock("../api/topics", () => ({
  fetchTopics: vi.fn().mockResolvedValue([
    { topic_id: 9, topic_name: "Digital Preservation", description: "", icon: "",
      publication_count: 4, researcher_count: 2, source: "derived" },
  ]),
}));

const paper: Publication = {
  publication_id: 5371,
  title: "Database Preservation",
  abstract: "How to keep databases readable.",
  doi: "10.1/x",
  publication_year: 2015,
  journal_name: "IJACSA",
  publication_type: "journal",
  citation_count: 2,
  campus: "",
  authors: [
    { researcher_id: 8, full_name: "Arif Ur Rahman" },
    { researcher_id: null, full_name: "Gabriel David" },
  ],
  topics: [],
  topic_names: ["Digital Preservation", "Unlisted Area"],
  source: "openalex",
};

function renderAt(id: number) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/publications/${id}`]}>
        <Routes>
          <Route path="/publications/:id" element={<PublicationDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PublicationDetail", () => {
  beforeEach(() => {
    vi.mocked(fetchPublication).mockResolvedValue(paper);
    vi.mocked(fetchRelatedPublications).mockResolvedValue([
      { ...paper, publication_id: 2, title: "Preserving archives" },
    ]);
  });

  it("links known authors to their profiles and names the others", async () => {
    renderAt(5371);
    const arif = await screen.findByRole("link", { name: "Arif Ur Rahman" });
    expect(arif).toHaveAttribute("href", "/researchers/8");
    expect(screen.queryByRole("link", { name: "Gabriel David" })).toBeNull();
    expect(screen.getByText(/Gabriel David/)).toBeInTheDocument();
  });

  it("links an area only when it has a page", async () => {
    renderAt(5371);
    expect(await screen.findByRole("link", { name: "Digital Preservation" })).toHaveAttribute(
      "href",
      "/topics/9",
    );
    expect(screen.queryByRole("link", { name: "Unlisted Area" })).toBeNull();
  });

  it("lists papers to read next", async () => {
    renderAt(5371);
    expect(await screen.findByRole("link", { name: "Preserving archives" })).toHaveAttribute(
      "href",
      "/publications/2",
    );
  });

  it("says plainly when there is no such paper", async () => {
    vi.mocked(fetchPublication).mockRejectedValue(new ApiError(404, "Publication not found"));
    renderAt(1);
    expect(await screen.findByText(/don’t have a publication at this address/)).toBeInTheDocument();
  });
});
