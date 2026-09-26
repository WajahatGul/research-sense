import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { approveClaim, fetchPendingClaims, rejectClaim, type PendingClaim } from "../../api/auth";
import { ClaimsQueue } from "./ClaimsQueue";

vi.mock("../../api/auth", () => ({
  fetchPendingClaims: vi.fn(),
  approveClaim: vi.fn(),
  rejectClaim: vi.fn(),
}));

const claim: PendingClaim = {
  id: 3,
  orcid_id: "0000-0001-8239-2033",
  researcher_id: 8,
  profile_name: "Arif Ur Rahman",
  profile_department: "Computer Science",
  profile_campus: "Islamabad (E-8)",
  orcid_names: ["Arif Ur Rahman"],
  orcid_employers: ["Bahria University"],
  submitted_at: "2026-09-26T15:40:24+00:00",
  competing_claims: 1,
};

function renderQueue() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ClaimsQueue />
    </QueryClientProvider>,
  );
}

describe("ClaimsQueue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchPendingClaims).mockResolvedValue([claim]);
  });

  it("shows the ORCID evidence next to the profile", async () => {
    renderQueue();
    expect(await screen.findByText("Arif Ur Rahman")).toBeInTheDocument();
    expect(screen.getByText("Bahria University")).toBeInTheDocument();
    expect(screen.getByText("1 other claim on this profile")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /0000-0001-8239-2033/ })).toHaveAttribute(
      "href",
      "https://orcid.org/0000-0001-8239-2033",
    );
  });

  it("approves a claim", async () => {
    vi.mocked(approveClaim).mockResolvedValue({
      status: "approved", message: "Claim approved.", token: null, role: "researcher",
      researcher_id: 8, full_name: "Arif Ur Rahman",
    });
    renderQueue();
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await waitFor(() => expect(approveClaim).toHaveBeenCalledWith(3, expect.anything()));
  });

  it("rejects with a reason", async () => {
    vi.mocked(rejectClaim).mockResolvedValue({ status: "rejected" });
    renderQueue();
    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
    fireEvent.change(screen.getByPlaceholderText("Reason shown to the claimant"), {
      target: { value: "Not on the staff list" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirm reject" }));
    await waitFor(() => expect(rejectClaim).toHaveBeenCalledWith(3, "Not on the staff list"));
  });

  it("says when nothing is waiting", async () => {
    vi.mocked(fetchPendingClaims).mockResolvedValue([]);
    renderQueue();
    expect(await screen.findByText("No claims waiting for review.")).toBeInTheDocument();
  });
});
