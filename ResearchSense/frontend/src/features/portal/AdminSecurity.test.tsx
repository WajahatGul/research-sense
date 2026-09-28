import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchMe } from "../../api/auth";
import { AdminSecurity } from "./AdminSecurity";

vi.mock("../../api/auth", () => ({ fetchMe: vi.fn(), getToken: () => "t" }));

const responses: Record<string, unknown> = {
  "/api/admin/admins": [
    { username: "admin", active: 1, weak_password: 1, created_at: "2026-09-28T10:00:00", created_by: "setup (.env)" },
    { username: "sara", active: 0, weak_password: 0, created_at: "2026-09-28T11:00:00", created_by: "admin" },
  ],
  "/api/admin/activity?limit=30": [
    { id: 2, at: "2026-09-28T11:05:00", actor: "admin", action: "admin.deactivated", target: "sara", detail: "" },
    { id: 1, at: "2026-09-28T11:00:00", actor: "admin", action: "claim.approved", target: "claim 3", detail: "Arif Ur Rahman" },
  ],
};

function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AdminSecurity />
    </QueryClientProvider>,
  );
}

describe("AdminSecurity", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
      ok: true,
      json: async () => responses[url] ?? {},
    })));
  });

  it("asks an admin with the settings password to change it", async () => {
    vi.mocked(fetchMe).mockResolvedValue({
      role: "admin", orcid_id: null, researcher_id: null, full_name: "admin",
      uploads: [], password_weak: true,
    });
    renderIt();
    expect(await screen.findByRole("heading", { name: "Change your password" })).toBeInTheDocument();
  });

  it("lists administrators and what they did, in plain words", async () => {
    vi.mocked(fetchMe).mockResolvedValue({
      role: "admin", orcid_id: null, researcher_id: null, full_name: "admin", uploads: [],
    });
    renderIt();
    expect(await screen.findByText(/deactivated administrator/)).toBeInTheDocument();
    expect(screen.getByText(/approved a profile claim/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reactivate" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Change your password" })).toBeNull();
  });
});
