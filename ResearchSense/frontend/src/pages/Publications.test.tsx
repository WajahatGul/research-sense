import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Paginated, Publication } from "../types";
import { fetchPublications, fetchPublicationYears } from "../api/publications";
import { fetchCampuses, fetchDepartments } from "../api/researchers";
import Publications from "./Publications";

vi.mock("../api/publications", () => ({
  fetchPublications: vi.fn(),
  fetchPublicationYears: vi.fn(),
}));

vi.mock("../api/researchers", () => ({
  fetchCampuses: vi.fn(),
  fetchDepartments: vi.fn(),
}));

const mockFetchPublications = vi.mocked(fetchPublications);
const mockFetchPublicationYears = vi.mocked(fetchPublicationYears);
const mockFetchCampuses = vi.mocked(fetchCampuses);
const mockFetchDepartments = vi.mocked(fetchDepartments);

const publication: Publication = {
  publication_id: 1,
  title: "A Great Paper",
  abstract: "",
  doi: null,
  publication_year: 2026,
  journal_name: "Journal of Things",
  publication_type: "journal",
  citation_count: 3,
  campus: "Islamabad (E-8)",
  authors: [],
  topics: [],
  source: "seed",
};

const publicationPage: Paginated<Publication> = {
  items: [publication],
  total: 1,
  page: 1,
  page_size: 10,
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Publications />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchPublicationYears.mockResolvedValue([2024, 2025, 2026]);
  mockFetchCampuses.mockResolvedValue(["Islamabad (E-8)"]);
  mockFetchDepartments.mockResolvedValue(["Computer Science"]);
  mockFetchPublications.mockResolvedValue(publicationPage);
});

describe("Publications", () => {
  it("does not fetch publications on mount", async () => {
    renderPage();

    await waitFor(() => expect(mockFetchPublicationYears).toHaveBeenCalled());
    expect(mockFetchPublications).not.toHaveBeenCalled();
  });

  it("shows the pre-search empty prompt", async () => {
    renderPage();

    expect(
      await screen.findByText(
        "Choose your filters and press Search to see publications.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the coverage data note", async () => {
    renderPage();

    expect(
      await screen.findByText(/reflects only the publications ResearchSense/),
    ).toBeInTheDocument();
  });

  it("fetches publications after Search is pressed", async () => {
    renderPage();

    const searchButton = await screen.findByRole("button", {
      name: "Search publications",
    });
    fireEvent.click(searchButton);

    await waitFor(() => expect(mockFetchPublications).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("A Great Paper")).toBeInTheDocument();
  });

  it("renders exactly one Search button", async () => {
    renderPage();

    await screen.findByRole("button", { name: "Search publications" });
    const searchButtons = screen.getAllByRole("button", { name: /search/i });
    expect(searchButtons).toHaveLength(1);
  });

  it("fetches publications when Enter is pressed in the search input", async () => {
    renderPage();

    const input = await screen.findByPlaceholderText("Search publication titles…");
    fireEvent.change(input, { target: { value: "great paper" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => expect(mockFetchPublications).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("A Great Paper")).toBeInTheDocument();
  });

  it("does not refetch when a filter changes without pressing Search", async () => {
    renderPage();

    const searchButton = await screen.findByRole("button", {
      name: "Search publications",
    });
    fireEvent.click(searchButton);
    await waitFor(() => expect(mockFetchPublications).toHaveBeenCalledTimes(1));

    const campusSelect = screen.getByLabelText("Filter by campus");
    fireEvent.change(campusSelect, { target: { value: "Islamabad (E-8)" } });

    expect(mockFetchPublications).toHaveBeenCalledTimes(1);
  });
});
