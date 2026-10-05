import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Paginated, Researcher } from "../types";
import {
  fetchAcademicRanks,
  fetchCampuses,
  fetchDepartments,
  fetchResearchers,
} from "../api/researchers";
import { fetchStats } from "../api/stats";
import Researchers from "./Researchers";

vi.mock("../api/researchers", () => ({
  fetchResearchers: vi.fn(),
  fetchCampuses: vi.fn(),
  fetchDepartments: vi.fn(),
  fetchAcademicRanks: vi.fn(),
}));

vi.mock("../api/stats", () => ({ fetchStats: vi.fn() }));

const mockFetchResearchers = vi.mocked(fetchResearchers);
const mockFetchCampuses = vi.mocked(fetchCampuses);
const mockFetchDepartments = vi.mocked(fetchDepartments);
const mockFetchAcademicRanks = vi.mocked(fetchAcademicRanks);
const mockFetchStats = vi.mocked(fetchStats);

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

function renderPage(url = "/researchers") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Researchers />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.search}</output>;
}

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchCampuses.mockResolvedValue(["Islamabad (E-8)"]);
  mockFetchDepartments.mockResolvedValue(["Computer Science"]);
  mockFetchAcademicRanks.mockResolvedValue(["Professor"]);
  mockFetchResearchers.mockResolvedValue(researcherPage);
  mockFetchStats.mockResolvedValue({
    researchers: 12,
    researchers_extended: 4000,
    publications: 40,
    projects: 2,
    topics: 5,
    departments: 3,
    campuses: 1,
  });
});

describe("Researchers", () => {
  it("restores filters and page from the URL (Back, refresh, shared link)", async () => {
    renderPage("/researchers?campus=Karachi&department=Computer%20Science&page=2");

    await waitFor(() =>
      expect(mockFetchResearchers).toHaveBeenCalledWith(
        expect.objectContaining({
          campus: "Karachi",
          department: "Computer Science",
          page: 2,
        }),
      ),
    );
  });

  it("records a submitted search in the URL", async () => {
    renderPage();

    const input = await screen.findByPlaceholderText("Search researchers…");
    fireEvent.change(input, { target: { value: "ayesha" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() =>
      expect(screen.getByTestId("location").textContent).toBe("?q=ayesha"),
    );
  });

  it("fetches the first page of researchers on mount", async () => {
    renderPage();

    await waitFor(() => expect(mockFetchResearchers).toHaveBeenCalled());
  });

  it("shows researchers by default without needing a search", async () => {
    renderPage();

    expect(await screen.findByText("Dr. Ayesha Khan")).toBeInTheDocument();
  });

  it("reports coverage from the live stats, not a hardcoded number", async () => {
    renderPage();

    // The counts must match whatever the API reports — a workspace holding one
    // researcher used to be told it had 358.
    expect(
      await screen.findByText(/12 profiles across 3 departments/),
    ).toBeInTheDocument();
  });

  it("explains that authors without a directory profile are searchable", async () => {
    renderPage();

    expect(
      await screen.findByText(/A further 4,000 authors have published here/),
    ).toBeInTheDocument();
  });

  it("still reads as a sentence before the counts arrive", async () => {
    mockFetchStats.mockReturnValue(new Promise(() => {})); // never resolves
    renderPage();

    const note = await screen.findByText(/This directory lists the faculty/);
    expect(note.textContent).toContain("has full details for.");
    expect(note.textContent).not.toContain("for .");
  });

  it("applies a filter the moment it is chosen", async () => {
    renderPage();

    await screen.findByText("Dr. Ayesha Khan");
    fireEvent.change(screen.getByLabelText("Filter by designation"), {
      target: { value: "Professor" },
    });

    await waitFor(() =>
      expect(mockFetchResearchers).toHaveBeenLastCalledWith(
        expect.objectContaining({ designation: "Professor" }),
      ),
    );
  });

  it("renders exactly one Search button, the search box's own", async () => {
    renderPage();

    await screen.findByText("Dr. Ayesha Khan");
    const searchButtons = screen.getAllByRole("button", { name: /^search$/i });
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

  it("searches by name when Enter is pressed in the search input", async () => {
    renderPage();

    const input = await screen.findByPlaceholderText("Search researchers…");
    fireEvent.change(input, { target: { value: "ayesha" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() =>
      expect(mockFetchResearchers).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: "ayesha" }),
      ),
    );
    expect(await screen.findByText("Dr. Ayesha Khan")).toBeInTheDocument();
  });
});
