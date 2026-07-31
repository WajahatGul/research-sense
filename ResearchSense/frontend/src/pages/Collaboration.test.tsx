import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CollaborationSuggestion, Paginated, Researcher, ResearcherDetail } from "../types";
import { fetchCollaborators, fetchResearcher, fetchResearchers } from "../api/researchers";
import Collaboration from "./Collaboration";

vi.mock("../api/researchers", () => ({
  fetchResearchers: vi.fn(),
  fetchResearcher: vi.fn(),
  fetchCollaborators: vi.fn(),
}));

const mockFetchResearchers = vi.mocked(fetchResearchers);
const mockFetchResearcher = vi.mocked(fetchResearcher);
const mockFetchCollaborators = vi.mocked(fetchCollaborators);

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

const detail: ResearcherDetail = {
  ...researcher,
  profile_bio: "",
  education: "",
  google_scholar_id: null,
  scopus_id: null,
  publications: [],
  collaborators: [],
  international_collaborations: [],
};

const collaborator: CollaborationSuggestion = {
  researcher_id: 2,
  full_name: "Dr. Bilal Ahmed",
  designation: "Associate Professor",
  department: "Electrical Engineering",
  campus: "Lahore",
  similarity_score: 0.8,
  shared_topics: ["Machine Learning"],
  shared_count: 2,
  copublications: 1,
  past_coauthor: true,
  same_campus: false,
  relevance: 0.9,
  international: false,
};

const researcherPage: Paginated<Researcher> = {
  items: [researcher],
  total: 1,
  page: 1,
  page_size: 100,
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Collaboration />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Collaboration", () => {
  it("does not fetch researcher detail or collaborators on mount", async () => {
    mockFetchResearchers.mockResolvedValue(researcherPage);
    mockFetchResearcher.mockImplementation(() => new Promise(() => {}));
    mockFetchCollaborators.mockImplementation(() => new Promise(() => {}));

    renderPage();

    await waitFor(() => expect(mockFetchResearchers).toHaveBeenCalled());
    expect(mockFetchResearcher).not.toHaveBeenCalled();
    expect(mockFetchCollaborators).not.toHaveBeenCalled();
  });

  it("shows the pick-a-researcher prompt before a researcher is selected", async () => {
    mockFetchResearchers.mockResolvedValue(researcherPage);
    mockFetchResearcher.mockImplementation(() => new Promise(() => {}));
    mockFetchCollaborators.mockImplementation(() => new Promise(() => {}));

    renderPage();

    expect(
      await screen.findByText(
        "Pick a researcher to see who they could collaborate with.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("fetches researcher detail and collaborators once a researcher is selected", async () => {
    mockFetchResearchers.mockResolvedValue(researcherPage);
    mockFetchResearcher.mockResolvedValue(detail);
    mockFetchCollaborators.mockResolvedValue([collaborator]);

    renderPage();

    const select = await screen.findByLabelText("Select a researcher");
    expect(select).toHaveValue("");
    await screen.findByText("Dr. Ayesha Khan — Professor");

    fireEvent.change(select, { target: { value: "1" } });

    await waitFor(() => expect(mockFetchResearcher).toHaveBeenCalledWith(1));
    await waitFor(() =>
      expect(mockFetchCollaborators).toHaveBeenCalledWith(1, "relevance"),
    );
  });

  it("shows a loader before the collaborators query resolves", async () => {
    mockFetchResearchers.mockResolvedValue(researcherPage);
    mockFetchResearcher.mockImplementation(() => new Promise(() => {}));
    mockFetchCollaborators.mockImplementation(() => new Promise(() => {}));

    renderPage();

    const select = await screen.findByLabelText("Select a researcher");
    await screen.findByText("Dr. Ayesha Khan — Professor");
    fireEvent.change(select, { target: { value: "1" } });

    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
  });

  it("shows the empty state once collaborators resolve to an empty list", async () => {
    mockFetchResearchers.mockResolvedValue(researcherPage);
    mockFetchResearcher.mockResolvedValue(detail);
    mockFetchCollaborators.mockResolvedValue([]);

    renderPage();

    const select = await screen.findByLabelText("Select a researcher");
    await screen.findByText("Dr. Ayesha Khan — Professor");
    fireEvent.change(select, { target: { value: "1" } });

    expect(
      await screen.findByText(/no shared-area or co-authored collaborators found/i),
    ).toBeInTheDocument();
  });

  it("renders all five sort options once collaborator rows are present", async () => {
    mockFetchResearchers.mockResolvedValue(researcherPage);
    mockFetchResearcher.mockResolvedValue(detail);
    mockFetchCollaborators.mockResolvedValue([collaborator]);

    renderPage();

    const researcherSelect = await screen.findByLabelText("Select a researcher");
    await screen.findByText("Dr. Ayesha Khan — Professor");
    fireEvent.change(researcherSelect, { target: { value: "1" } });

    const select = await screen.findByLabelText("Sort collaborators");
    expect(select.querySelectorAll("option")).toHaveLength(5);
  });
});
