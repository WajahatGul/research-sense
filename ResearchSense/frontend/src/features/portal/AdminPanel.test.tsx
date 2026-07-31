import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PendingPaper } from "../../api/auth";
import {
  approvePaper,
  fetchAdminAccounts,
  fetchPendingPapers,
  fetchRefreshStatus,
  rejectPaper,
  setAccountActive,
  triggerRefresh,
} from "../../api/auth";
import { AdminPanel } from "./AdminPanel";

vi.mock("../../api/auth", () => ({
  approvePaper: vi.fn(),
  fetchAdminAccounts: vi.fn(),
  fetchPendingPapers: vi.fn(),
  fetchRefreshStatus: vi.fn(),
  rejectPaper: vi.fn(),
  setAccountActive: vi.fn(),
  triggerRefresh: vi.fn(),
}));

const mockApprovePaper = vi.mocked(approvePaper);
const mockFetchAdminAccounts = vi.mocked(fetchAdminAccounts);
const mockFetchPendingPapers = vi.mocked(fetchPendingPapers);
const mockFetchRefreshStatus = vi.mocked(fetchRefreshStatus);
const mockRejectPaper = vi.mocked(rejectPaper);
const mockSetAccountActive = vi.mocked(setAccountActive);
const mockTriggerRefresh = vi.mocked(triggerRefresh);

const pendingPaper: PendingPaper = {
  id: 42,
  kind: "publication",
  researcher_id: 7,
  title: "A Great Paper Title",
  submitted_at: "2026-07-01T00:00:00Z",
  record: { journal_name: "Journal of Things", publication_year: 2026, doi: "10.1/x" },
};

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AdminPanel onSignOut={vi.fn()} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockFetchAdminAccounts.mockResolvedValue([]);
  mockFetchRefreshStatus.mockResolvedValue({ last_refresh: null, due: false });
  mockApprovePaper.mockResolvedValue({ status: "ok" });
  mockRejectPaper.mockResolvedValue({ status: "ok" });
  mockSetAccountActive.mockResolvedValue({});
  mockTriggerRefresh.mockResolvedValue({});
});

describe("AdminPanel", () => {
  it("renders a pending row's title", async () => {
    mockFetchPendingPapers.mockResolvedValue([pendingPaper]);

    renderPanel();

    expect(await screen.findByText("A Great Paper Title")).toBeInTheDocument();
  });

  it("calls approvePaper with the row id when Approve is clicked", async () => {
    mockFetchPendingPapers.mockResolvedValue([pendingPaper]);

    renderPanel();

    await screen.findByText("A Great Paper Title");
    const approveButton = await screen.findByRole("button", { name: "Approve" });
    fireEvent.click(approveButton);

    expect(mockApprovePaper).toHaveBeenCalledWith(42);
  });

  it("renders the empty state when there are no pending papers", async () => {
    mockFetchPendingPapers.mockResolvedValue([]);

    renderPanel();

    expect(
      await screen.findByText("No papers waiting for review."),
    ).toBeInTheDocument();
  });
});
