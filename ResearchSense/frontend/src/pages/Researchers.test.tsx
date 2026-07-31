import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Paginated, Researcher } from "../types";
import {
  fetchAcademicRanks,
  fetchCampuses,
  fetchDepartments,
  fetchResearchers,
} from "../api/researchers";
import Researchers from "./Researchers";

vi.mock("../api/researchers", () => ({
  fetchResearchers: vi.fn(),
  fetchCampuses: vi.fn(),
  fetchDepartments: vi.fn(),
  fetchAcademicRanks: vi.fn(),
}));

const mockFetchResearchers = vi.mocked(fetchResearchers);
const mockFetchCampuses = vi.mocked(fetchCampuses);
const mockFetchDepartments = vi.mocked(fetchDepartments);
const mockFetchAcademicRanks = vi.mocked(fetchAcademicRanks);

const researcher: Researcher = {
  researcher_id: 1,
  full_name: "Dr. Ayesha Khan",
  designation: "Professor",
  department: "Computer Science",
  campus: "Islamabad (E-8)",
  institution: "NUST",
  email: null,
  orcid_id: null,
  photo_url: null,
  expertise: "",
  publication_count: 10,
  citation_count: 20,
  topics: [],
  source: "seed",
  research_areas: [],
};

const researcherPage: Paginated<Researcher> = {
  items: [researcher],
  total: 1,
  page: 1,
  page_size: 12,
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Researchers />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchCampuses.mockResolvedValue(["Islamabad (E-8)"]);
  mockFetchDepartments.mockResolvedValue(["Computer Science"]);
  mockFetchAcademicRanks.mockResolvedValue(["Professor"]);
  mockFetchResearchers.mockResolvedValue(researcherPage);
});

describe("Researchers", () => {
  it("does not fetch researchers on mount", async () => {
    renderPage();

    await waitFor(() => expect(mockFetchCampuses).toHaveBeenCalled());
    expect(mockFetchResearchers).not.toHaveBeenCalled();
  });

  it("shows the pre-search empty prompt", async () => {
    renderPage();

    expect(
      await screen.findByText(
        "Choose your filters and press Search to see researchers.",
      ),
    ).toBeInTheDocument();
  });

  it("fetches researchers after Search is pressed", async () => {
    renderPage();

    const searchButton = await screen.findByRole("button", {
      name: "Search researchers",
    });
    fireEvent.click(searchButton);

    await waitFor(() => expect(mockFetchResearchers).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Dr. Ayesha Khan")).toBeInTheDocument();
  });

  it("renders exactly one Search button", async () => {
    renderPage();

    await screen.findByRole("button", { name: "Search researchers" });
    const searchButtons = screen.getAllByRole("button", { name: /search/i });
    expect(searchButtons).toHaveLength(1);
  });

  it("populates the designation dropdown from the academic ranks endpoint", async () => {
    mockFetchAcademicRanks.mockResolvedValue([
      "Senior Assistant Professor",
      "Senior Associate Professor",
      "Senior Professor",
    ]);

    renderPage();

    const select = await screen.findByLabelText("Filter by designation");
    await waitFor(() => expect(mockFetchAcademicRanks).toHaveBeenCalled());
    const options = Array.from(select.querySelectorAll("option")).map(
      (o) => o.textContent,
    );
    expect(options).toEqual([
      "All ranks",
      "Senior Assistant Professor",
      "Senior Associate Professor",
      "Senior Professor",
    ]);
  });

  it("fetches researchers when Enter is pressed in the search input", async () => {
    renderPage();

    const input = await screen.findByPlaceholderText("Search researchers…");
    fireEvent.change(input, { target: { value: "ayesha" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => expect(mockFetchResearchers).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Dr. Ayesha Khan")).toBeInTheDocument();
  });
});
