import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Paginated, Publication, Researcher, Topic } from "../types";
import { fetchPublications } from "../api/publications";
import { fetchResearchers } from "../api/researchers";
import { fetchTopics } from "../api/topics";
import Search from "./Search";

vi.mock("../api/researchers", () => ({ fetchResearchers: vi.fn() }));
vi.mock("../api/publications", () => ({ fetchPublications: vi.fn() }));
vi.mock("../api/topics", () => ({ fetchTopics: vi.fn() }));

const person: Researcher = {
  researcher_id: 1,
  full_name: "Dr. Ayesha Khan",
  designation: "Professor",
  department: "Computer Science",
  campus: "Islamabad (E-8)",
  institution: "Bahria University",
  email: null,
  orcid_id: null,
  photo_url: null,
  expertise: "",
  publication_count: 3,
  citation_count: 9,
  topics: [],
  source: "seed",
  research_areas: [],
};

const paper = {
  publication_id: 7,
  title: "Learning to route packets",
  publication_year: 2024,
  authors: [],
  topics: [],
} as unknown as Publication;

const area: Topic = {
  topic_id: 3,
  topic_name: "Machine Learning",
  publication_count: 40,
  researcher_count: 9,
} as Topic;

function page<T>(items: T[], extra: Partial<Paginated<T>> = {}): Paginated<T> {
  return { items, total: items.length, page: 1, page_size: 6, ...extra };
}

function renderAt(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/search" element={<Search />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchResearchers).mockResolvedValue(page([person]));
  vi.mocked(fetchPublications).mockResolvedValue(page([paper]));
  vi.mocked(fetchTopics).mockResolvedValue([area]);
});

describe("Search", () => {
  it("shows researchers, research areas and publications together", async () => {
    renderAt("/search?q=learning");

    expect(await screen.findByText("Dr. Ayesha Khan")).toBeInTheDocument();
    expect(await screen.findByText("Learning to route packets")).toBeInTheDocument();
    expect(await screen.findByText("Machine Learning")).toBeInTheDocument();
  });

  it("says when results are for a corrected spelling", async () => {
    vi.mocked(fetchResearchers).mockResolvedValue(
      page([person], { corrected_query: "machine learning" }),
    );
    renderAt("/search?q=machin%20lerning");

    const note = await screen.findByText(/No exact matches for/);
    expect(note.textContent).toContain("machine learning");
  });

  it("offers ways forward when nothing matches", async () => {
    vi.mocked(fetchResearchers).mockResolvedValue(page([]));
    vi.mocked(fetchPublications).mockResolvedValue(page([]));
    vi.mocked(fetchTopics).mockResolvedValue([]);
    renderAt("/search?q=zzqxv");

    expect(await screen.findByText(/Nothing matches/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse research areas" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask the assistant" })).toBeInTheDocument();
  });
});
