import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Backups } from "./Backups";

vi.mock("../../api/auth", () => ({ getToken: () => "t" }));

describe("Backups", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({
        backups: [
          { name: "accounts-20260928-100000.db", at: "2026-09-28T10:00:00+00:00", size: 1,
            counts: { accounts: 1, claims: 3, corrections: 1, submissions: 0, audit_log: 12 } },
          { name: "accounts-20260927-100000.db", at: "2026-09-27T10:00:00+00:00", size: 1, counts: null },
        ],
      }),
    })));
  });

  it("says what each copy holds and will not restore a damaged one", async () => {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <Backups />
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/3 claims/, {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText(/damaged, cannot be restored/)).toBeInTheDocument();
    const buttons = screen.getAllByRole("button", { name: "Restore" });
    expect(buttons[0]).toBeEnabled();
    expect(buttons[1]).toBeDisabled();
  });
});
