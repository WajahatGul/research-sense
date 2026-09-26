import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
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

function Where() {
  return <output data-testid="where">{useLocation().search}</output>;
}

function renderPage(url = "/publications") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Publications />
        <Where />
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
  it("lists the newest publications on arrival", async () => {
    renderPage();

    expect(await screen.findByText("A Great Paper")).toBeInTheDocument();
    expect(mockFetchPublications).toHaveBeenCalledTimes(1);
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

    await waitFor(() => expect(mockFetchPublications).toHaveBeenCalled());
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

    await waitFor(() =>
      expect(mockFetchPublications).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: "great paper" }),
      ),
    );
    expect(await screen.findByText("A Great Paper")).toBeInTheDocument();
  });

  it("does not refetch when a filter changes without pressing Search", async () => {
    renderPage();

    await screen.findByText("A Great Paper");
    const callsBefore = mockFetchPublications.mock.calls.length;

    const campusSelect = screen.getByLabelText("Filter by campus");
    fireEvent.change(campusSelect, { target: { value: "Islamabad (E-8)" } });

    expect(mockFetchPublications).toHaveBeenCalledTimes(callsBefore);
  });

  it("says how many filters are active on the folded filter button", async () => {
    renderPage();

    const toggle = await screen.findByRole("button", { name: "Filters" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    fireEvent.change(screen.getByLabelText("Filter by campus"), {
      target: { value: "Islamabad (E-8)" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search publications" }));

    expect(
      await screen.findByRole("button", { name: "Hide filters · 1 active" }),
    ).toHaveAttribute("aria-expanded", "true");
  });

  it("keeps the applied filters in the URL", async () => {
    renderPage();
    await screen.findByText("A Great Paper");
    fireEvent.change(screen.getByLabelText("Filter by year"), { target: { value: "2025" } });
    fireEvent.click(screen.getByRole("button", { name: "Search publications" }));
    expect(screen.getByTestId("where").textContent).toBe("?year=2025");
  });

  it("restores a shared or bookmarked link", async () => {
    renderPage("/publications?q=graph&type=book-chapter&page=2");
    await waitFor(() =>
      expect(mockFetchPublications).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: "graph", publication_type: "book-chapter", page: 2 }),
      ),
    );
    expect(screen.getByLabelText("Search publication titles…")).toHaveValue("graph");
  });
});
