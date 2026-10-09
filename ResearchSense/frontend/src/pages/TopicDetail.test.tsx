import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Publication, Researcher, Topic } from "../types";
import { ApiError } from "../api/client";
import { fetchPublications } from "../api/publications";
import { fetchResearchers } from "../api/researchers";
import { fetchTopic } from "../api/topics";
import TopicDetail from "./TopicDetail";

vi.mock("../api/researchers", () => ({ fetchResearchers: vi.fn() }));
vi.mock("../api/publications", () => ({ fetchPublications: vi.fn() }));
vi.mock("../api/topics", () => ({ fetchTopic: vi.fn() }));

const topic = {
  topic_id: 3,
  topic_name: "Wireless Sensor Networks",
  publication_count: 12,
  researcher_count: 2,
} as Topic;

const person = {
  researcher_id: 9,
  full_name: "Dr. Sana Iqbal",
  designation: "Assistant Professor",
  department: "Computer Engineering",
  campus: "Karachi",
  topics: [],
  research_areas: [],
  publication_count: 4,
  citation_count: 10,
} as unknown as Researcher;

const paper = {
  publication_id: 1,
  title: "Energy-aware routing for sensor fields",
  publication_year: 2025,
  authors: [],
  topics: [],
} as unknown as Publication;

function renderAt(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/topics/:id" element={<TopicDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchTopic).mockResolvedValue(topic);
  vi.mocked(fetchResearchers).mockResolvedValue({ items: [person], total: 1, page: 1, page_size: 100 });
  vi.mocked(fetchPublications).mockResolvedValue({ items: [paper], total: 12, page: 1, page_size: 5 });
});

describe("TopicDetail", () => {
  it("shows the people working in the area, not just its papers", async () => {
    renderAt("/topics/3");

    expect(await screen.findByRole("heading", { name: "Wireless Sensor Networks" })).toBeInTheDocument();
    expect(await screen.findByText("Dr. Sana Iqbal")).toBeInTheDocument();
    expect(await screen.findByText("Energy-aware routing for sensor fields")).toBeInTheDocument();
    expect(fetchResearchers).toHaveBeenCalledWith(expect.objectContaining({ topic_id: 3 }));
  });

  it("links to the full publication list for the area", async () => {
    renderAt("/topics/3");

    const link = await screen.findByRole("link", { name: /See all 12 publications/ });
    expect(link.getAttribute("href")).toBe("/publications?topic_id=3");
  });

  it("explains a missing area instead of showing a generic error", async () => {
    vi.mocked(fetchTopic).mockRejectedValue(new ApiError(404, "Topic not found"));
    renderAt("/topics/999");

    expect(await screen.findByText(/don’t have a research area/)).toBeInTheDocument();
  });
});
