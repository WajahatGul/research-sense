import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ResearcherDetail } from "../types";
import { fetchResearcher } from "../api/researchers";
import { fetchClaimedIds } from "../api/auth";
import ResearcherProfile from "./ResearcherProfile";

vi.mock("../api/researchers", () => ({
  fetchResearcher: vi.fn(),
}));

vi.mock("../api/auth", () => ({
  fetchClaimedIds: vi.fn(),
}));

const mockFetchResearcher = vi.mocked(fetchResearcher);
const mockFetchClaimedIds = vi.mocked(fetchClaimedIds);

function baseDetail(overrides: Partial<ResearcherDetail> = {}): ResearcherDetail {
  return {
    researcher_id: 1,
    full_name: "Dr. Ayesha Khan",
    designation: "Professor",
    department: "Computer Science",
    campus: "Islamabad (E-8)",
    institution: "Bahria",
    email: null,
    orcid_id: null,
    photo_url: null,
    expertise: "",
    publication_count: 0,
    citation_count: 0,
    topics: [],
    source: "seed",
    research_areas: [],
    profile_bio: "",
    education: "",
    google_scholar_id: null,
    scopus_id: null,
    publications: [],
    collaborators: [],
    international_collaborations: [],
    ...overrides,
  };
}

function renderProfile(id: string, search = "") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/researchers/${id}${search}`]}>
        <Routes>
          <Route path="/researchers/:id" element={<ResearcherProfile />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchClaimedIds.mockResolvedValue([]);
});

describe("ResearcherProfile international collaborations toggle", () => {
  function intlList(n: number) {
    return Array.from({ length: n }, (_, i) => ({
      institution: `Institution ${i + 1}`,
      country: "US",
    }));
  }

  it("caps international collaborations at 10 with a '+N more' toggle button", async () => {
    mockFetchResearcher.mockResolvedValue(
      baseDetail({ international_collaborations: intlList(18) }),
    );

    renderProfile("1");

    await screen.findByText(/Institution 1 ·/);
    expect(screen.queryByText(/Institution 11 ·/)).not.toBeInTheDocument();

    const toggle = screen.getByRole("button", { name: "+8 more" });
    fireEvent.click(toggle);

    expect(await screen.findByText(/Institution 11 ·/)).toBeInTheDocument();
    expect(screen.getByText(/Institution 18 ·/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show fewer" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show fewer" }));
    await waitFor(() =>
      expect(screen.queryByText(/Institution 11 ·/)).not.toBeInTheDocument(),
    );
  });
});

describe("ResearcherProfile shared-paper-first (with param)", () => {
  function pub(id: number, year: number, authorIds: number[]) {
    return {
      publication_id: id,
      title: `Paper ${id}`,
      publication_year: year,
      journal_name: "J",
      citation_count: 0,
      doi: null,
      author_ids: authorIds,
    };
  }

  it("reorders publications co-authored with the origin researcher to the top and shows a caption", async () => {
    mockFetchResearcher.mockImplementation((id: number) => {
      if (id === 1) {
        return Promise.resolve(
          baseDetail({
            researcher_id: 1,
            publications: [
              pub(1, 2022, [1]),
              pub(2, 2021, [1, 2]),
              pub(3, 2020, [1]),
            ],
          }),
        );
      }
      return Promise.resolve(baseDetail({ researcher_id: 2, full_name: "Dr. Bilal Ahmed" }));
    });

    renderProfile("1", "?with=2");

    await screen.findByText(/Papers co-authored with Dr\. Bilal Ahmed shown first/);

    const titles = screen
      .getAllByText(/^Paper \d$/)
      .map((el) => el.textContent);
    expect(titles).toEqual(["Paper 2", "Paper 1", "Paper 3"]);
  });

  it("omits the caption when there is no with param", async () => {
    mockFetchResearcher.mockResolvedValue(
      baseDetail({ publications: [pub(1, 2022, [1])] }),
    );

    renderProfile("1");

    await screen.findByText("Paper 1");
    expect(screen.queryByText(/shown first/)).not.toBeInTheDocument();
  });

  it("degrades gracefully when the origin researcher fetch fails", async () => {
    mockFetchResearcher.mockImplementation((id: number) => {
      if (id === 1) {
        return Promise.resolve(baseDetail({ researcher_id: 1, publications: [pub(1, 2022, [1])] }));
      }
      return Promise.reject(new Error("not found"));
    });

    renderProfile("1", "?with=999");

    await screen.findByText("Paper 1");
    expect(screen.queryByText(/shown first/)).not.toBeInTheDocument();
  });
});
