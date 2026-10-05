import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  confirmSamePerson,
  dismissSuggestion,
  fetchMyCorrections,
  reportNotMine,
} from "../../api/corrections";
import type { Publication } from "../../types";
import { YourRecord } from "./YourRecord";

vi.mock("../../api/corrections", () => ({
  fetchMyCorrections: vi.fn(),
  reportNotMine: vi.fn(),
  confirmSamePerson: vi.fn(),
  dismissSuggestion: vi.fn(),
}));

const paper = {
  publication_id: 5371,
  title: "Database Preservation",
  publication_year: 2015,
  authors: [],
  topics: [],
} as unknown as Publication;

function renderRecord() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <YourRecord papers={[paper]} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("YourRecord", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchMyCorrections).mockResolvedValue({
      corrections: [],
      suggestions: [
        {
          researcher_id: 8, profile_name: "Arif Ur Rahman", openalex_id: "A1",
          other_name: "Arif Ur Rehman", papers: [{ publication_id: 9, title: "Fish images", year: 2022 }],
          paper_count: 1, shared_coauthors: 0, shared_areas: [], score: 1,
        },
      ],
    });
    vi.mocked(reportNotMine).mockResolvedValue({ message: "Sent for review." });
    vi.mocked(confirmSamePerson).mockResolvedValue({ message: "Sent for review." });
    vi.mocked(dismissSuggestion).mockResolvedValue({ status: "recorded" });
  });

  it("asks whether a similar author record is also you", async () => {
    renderRecord();
    expect(await screen.findByText("Arif Ur Rehman")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Yes, this is me" }));
    await waitFor(() => expect(confirmSamePerson).toHaveBeenCalledWith("A1", expect.anything()));
  });

  it("dismisses a suggestion that is not you", async () => {
    renderRecord();
    fireEvent.click(await screen.findByRole("button", { name: "No, not me" }));
    await waitFor(() => expect(dismissSuggestion).toHaveBeenCalledWith("A1", expect.anything()));
  });

  it("sends 'not mine' for review with a reason", async () => {
    renderRecord();
    fireEvent.click(await screen.findByRole("button", { name: "Not mine" }));
    fireEvent.change(screen.getByPlaceholderText(/Optional: why/), {
      target: { value: "Different Arif" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send for review" }));
    await waitFor(() => expect(reportNotMine).toHaveBeenCalledWith(5371, "Different Arif"));
    expect(await screen.findByRole("status")).toHaveTextContent("Sent for review.");
  });
});
