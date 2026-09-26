import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Topic } from "../types";
import { fetchTopics } from "../api/topics";
import { fetchDepartments } from "../api/researchers";
import Topics from "./Topics";

vi.mock("../api/topics", () => ({ fetchTopics: vi.fn() }));
vi.mock("../api/researchers", () => ({ fetchDepartments: vi.fn() }));
vi.mock("../api/suggest", () => ({ fetchSuggestions: vi.fn().mockResolvedValue([]) }));

const topic = (id: number, name: string, pubs: number, people: number): Topic => ({
  topic_id: id,
  topic_name: name,
  description: "",
  icon: "",
  publication_count: pubs,
  researcher_count: people,
  source: "derived",
});

function Where() {
  return <output data-testid="where">{useLocation().search}</output>;
}

function renderAt(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/topics" element={<><Topics /><Where /></>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Research areas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchDepartments).mockResolvedValue(["Computer Science", "Psychology"]);
    vi.mocked(fetchTopics).mockResolvedValue(
      Array.from({ length: 60 }, (_, i) => topic(i + 1, `Area ${i + 1}`, i, 60 - i)),
    );
  });

  it("shows the largest areas first, a page at a time", async () => {
    renderAt("/topics");
    const cards = await screen.findAllByRole("heading", { level: 3 });
    expect(cards).toHaveLength(48);
    expect(cards[0].textContent).toBe("Area 60");
    fireEvent.click(screen.getByRole("button", { name: "Show 12 more" }));
    expect(await screen.findAllByRole("heading", { level: 3 })).toHaveLength(60);
  }, 15_000); // renders 108 cards; slow under a full parallel run

  it("sorts by researchers when asked", async () => {
    renderAt("/topics?sort=researchers");
    const cards = await screen.findAllByRole("heading", { level: 3 });
    expect(cards[0].textContent).toBe("Area 1");
  });

  it("filters by department through the URL", async () => {
    renderAt("/topics");
    await screen.findAllByRole("heading", { level: 3 });
    fireEvent.change(screen.getByLabelText("Filter by department"), {
      target: { value: "Psychology" },
    });
    expect(screen.getByTestId("where").textContent).toBe("?department=Psychology");
    expect(fetchTopics).toHaveBeenLastCalledWith("", "Psychology");
  });

  it("says plainly when a search finds nothing", async () => {
    vi.mocked(fetchTopics).mockResolvedValue([]);
    renderAt("/topics?q=zzz");
    expect(await screen.findByText(/No research area matches “zzz”/)).toBeTruthy();
  });
});
