import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { Outbox } from "./Outbox";

vi.mock("../../api/auth", () => ({ getToken: () => "t" }));

describe("Outbox", () => {
  it("says nothing leaves without a mail server and lets the admin send it on", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({
        mail_server: false,
        messages: [{
          id: 1, at: "2026-09-28T10:00:00+00:00", to_addr: "arif@example.org",
          subject: "Your ResearchSense profile is yours", body: "Dear Arif,\n\nApproved.",
          reason: "claim 1 approved", status: "not sent", error: null,
        }],
      }),
    })));
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <Outbox />
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Your ResearchSense profile is yours" }, { timeout: 5000 }));
    expect(screen.getByText(/No mail server is set/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Send from my mail" })).toHaveAttribute(
      "href", expect.stringMatching(/^mailto:arif@example\.org\?subject=/),
    );
  });
});
