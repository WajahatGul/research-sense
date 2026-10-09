import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { Usage } from "./Usage";

vi.mock("../../api/auth", () => ({ getToken: () => "t" }));

describe("Usage", () => {
  it("shows the funnel and what people could not find", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: true,
      json: async () => ({
        days: 30, visitors: 40, returning_visitors: 10, searches_without_results: 3,
        top_missed_searches: [{ query: "quantum biology", where: "researchers", times: 2 }],
        claims: { started: 5, sent_for_review: 2, profiles_claimed: 1 },
      }),
    })));
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <Usage />
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/came back on another day \(25%\)/, {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText(/“quantum biology”/)).toBeInTheDocument();
    expect(screen.getByText(/profile opened/)).toBeInTheDocument();
  });
});
