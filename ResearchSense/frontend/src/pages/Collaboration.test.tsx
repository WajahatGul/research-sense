import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  CollaborationSuggestion,
  Paginated,
  Researcher,
  ResearcherDetail,
} from "../types";
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

// Stands in for a researcher who would fall outside any preloaded "first
// page" of the roster (regression coverage for the bug where the typeahead
// filtered a single preloaded page instead of querying the server).
const moneeb: Researcher = {
  ...researcher,
  researcher_id: 99,
  full_name: "Moneeb Gohar",
  campus: "Islamabad (H-11)",
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

function page(items: Researcher[]): Paginated<Researcher> {
  return { items, total: items.length, page: 1, page_size: 8 };
}

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
  it("does not fetch researcher detail, collaborators, or researchers on mount", async () => {
    mockFetchResearcher.mockImplementation(() => new Promise(() => {}));
    mockFetchCollaborators.mockImplementation(() => new Promise(() => {}));

    renderPage();

    await screen.findByLabelText("Search researchers by name");
    expect(mockFetchResearchers).not.toHaveBeenCalled();
    expect(mockFetchResearcher).not.toHaveBeenCalled();
    expect(mockFetchCollaborators).not.toHaveBeenCalled();
  });

  it("shows the pick-a-researcher prompt before a researcher is selected", async () => {
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

  it("queries the server (not a preloaded array) with the typed name, debounced", async () => {
    mockFetchResearchers.mockResolvedValue(page([]));
    mockFetchResearcher.mockImplementation(() => new Promise(() => {}));
    mockFetchCollaborators.mockImplementation(() => new Promise(() => {}));

    renderPage();

    const input = await screen.findByLabelText("Search researchers by name");
    fireEvent.change(input, { target: { value: "moneeb" } });

    // Not fired immediately (debounced).
    expect(mockFetchResearchers).not.toHaveBeenCalled();

    await waitFor(() =>
      expect(mockFetchResearchers).toHaveBeenCalledWith({
        q: "moneeb",
        page_size: 8,
      }),
    );
  });

  it("finds a researcher who would not be present on any preloaded first page", async () => {
    // The mount call the old implementation made no longer exists, but even
    // if something loaded an initial page, it would return no Moneeb — only
    // the server-side `q` search does.
    mockFetchResearchers.mockImplementation((filters) => {
      if (filters?.q === "moneeb") return Promise.resolve(page([moneeb]));
      return Promise.resolve(page([]));
    });
    mockFetchResearcher.mockImplementation(() => new Promise(() => {}));
    mockFetchCollaborators.mockImplementation(() => new Promise(() => {}));

    renderPage();

    const input = await screen.findByLabelText("Search researchers by name");
    fireEvent.change(input, { target: { value: "moneeb" } });

    expect(
      await screen.findByRole("option", { name: /Moneeb Gohar/ }),
    ).toBeInTheDocument();
  });

  it("selects a researcher and loads their collaborators when a match is clicked", async () => {
    mockFetchResearchers.mockResolvedValue(page([researcher]));
    mockFetchResearcher.mockResolvedValue(detail);
    mockFetchCollaborators.mockResolvedValue([collaborator]);

    renderPage();

    const input = await screen.findByLabelText("Search researchers by name");
    fireEvent.change(input, { target: { value: "Ayesha" } });

    const option = await screen.findByRole("option", { name: /Dr\. Ayesha Khan/ });
    fireEvent.mouseDown(option);

    await waitFor(() => expect(mockFetchResearcher).toHaveBeenCalledWith(1));
    await waitFor(() =>
      expect(mockFetchCollaborators).toHaveBeenCalledWith(1, "relevance"),
    );
  });

  it("shows a no-match message when the query matches nobody", async () => {
    mockFetchResearchers.mockResolvedValue(page([]));
    mockFetchResearcher.mockImplementation(() => new Promise(() => {}));
    mockFetchCollaborators.mockImplementation(() => new Promise(() => {}));

    renderPage();

    const input = await screen.findByLabelText("Search researchers by name");
    fireEvent.change(input, { target: { value: "zzznotfound" } });

    expect(
      await screen.findByText("No researcher found matching 'zzznotfound'."),
    ).toBeInTheDocument();
  });

  it("shows a retry action when the researcher search fails", async () => {
    mockFetchResearchers.mockRejectedValue(new Error("boom"));
    mockFetchResearcher.mockImplementation(() => new Promise(() => {}));
    mockFetchCollaborators.mockImplementation(() => new Promise(() => {}));

    renderPage();

    const input = await screen.findByLabelText("Search researchers by name");
    fireEvent.change(input, { target: { value: "Ayesha" } });

    expect(
      await screen.findByText(/Could not load researchers/),
    ).toBeInTheDocument();
    const retryButton = screen.getByRole("button", { name: "Retry" });

    mockFetchResearchers.mockResolvedValue(page([researcher]));
    fireEvent.click(retryButton);

    await waitFor(() => expect(mockFetchResearchers).toHaveBeenCalledTimes(2));
  });

  it("does not query for a single-character search", async () => {
    mockFetchResearchers.mockResolvedValue(page([researcher]));
    mockFetchResearcher.mockImplementation(() => new Promise(() => {}));
    mockFetchCollaborators.mockImplementation(() => new Promise(() => {}));

    renderPage();

    const input = await screen.findByLabelText("Search researchers by name");
    fireEvent.change(input, { target: { value: "A" } });

    // Give the debounce timer plenty of time to have fired if it were going to.
    await new Promise((r) => setTimeout(r, 400));
    expect(mockFetchResearchers).not.toHaveBeenCalled();
  });

  it("shows a loader before the collaborators query resolves", async () => {
    mockFetchResearchers.mockResolvedValue(page([researcher]));
    mockFetchResearcher.mockImplementation(() => new Promise(() => {}));
    mockFetchCollaborators.mockImplementation(() => new Promise(() => {}));

    renderPage();

    const input = await screen.findByLabelText("Search researchers by name");
    fireEvent.change(input, { target: { value: "Ayesha" } });
    const option = await screen.findByRole("option", { name: /Dr\. Ayesha Khan/ });
    fireEvent.mouseDown(option);

    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
  });

  it("shows the empty state once collaborators resolve to an empty list", async () => {
    mockFetchResearchers.mockResolvedValue(page([researcher]));
    mockFetchResearcher.mockResolvedValue(detail);
    mockFetchCollaborators.mockResolvedValue([]);

    renderPage();

    const input = await screen.findByLabelText("Search researchers by name");
    fireEvent.change(input, { target: { value: "Ayesha" } });
    const option = await screen.findByRole("option", { name: /Dr\. Ayesha Khan/ });
    fireEvent.mouseDown(option);

    expect(
      await screen.findByText(/no shared-area or co-authored collaborators found/i),
    ).toBeInTheDocument();
  });

  it("renders all five sort options once collaborator rows are present", async () => {
    mockFetchResearchers.mockResolvedValue(page([researcher]));
    mockFetchResearcher.mockResolvedValue(detail);
    mockFetchCollaborators.mockResolvedValue([collaborator]);

    renderPage();

    const input = await screen.findByLabelText("Search researchers by name");
    fireEvent.change(input, { target: { value: "Ayesha" } });
    const option = await screen.findByRole("option", { name: /Dr\. Ayesha Khan/ });
    fireEvent.mouseDown(option);

    const select = await screen.findByLabelText("Sort collaborators");
    expect(select.querySelectorAll("option")).toHaveLength(5);
  });

  it("selects the highlighted match on Enter after arrowing down", async () => {
    mockFetchResearchers.mockResolvedValue(page([researcher]));
    mockFetchResearcher.mockResolvedValue(detail);
    mockFetchCollaborators.mockResolvedValue([collaborator]);

    renderPage();

    const input = await screen.findByLabelText("Search researchers by name");
    fireEvent.change(input, { target: { value: "Ayesha" } });
    await screen.findAllByRole("option");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(mockFetchResearcher).toHaveBeenCalledWith(1));
  });

  it("clears the query on Escape", async () => {
    mockFetchResearchers.mockResolvedValue(page([researcher]));
    mockFetchResearcher.mockImplementation(() => new Promise(() => {}));
    mockFetchCollaborators.mockImplementation(() => new Promise(() => {}));

    renderPage();

    const input = await screen.findByLabelText<HTMLInputElement>(
      "Search researchers by name",
    );
    fireEvent.change(input, { target: { value: "Ayesha" } });
    await screen.findAllByRole("option");

    fireEvent.keyDown(input, { key: "Escape" });

    expect(input.value).toBe("");
  });
});
