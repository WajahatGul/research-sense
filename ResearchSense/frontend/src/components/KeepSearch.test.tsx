import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { KeepSearch } from "./KeepSearch";

describe("KeepSearch", () => {
  it("is not offered until there is something to follow", () => {
    render(<KeepSearch kind="publications" filters={{ q: undefined }} />);
    expect(screen.queryByRole("button", { name: "Email me new matches" })).toBeNull();
  });

  it("keeps the search on screen and says to confirm by email", async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({ status: "check your email" }) }));
    vi.stubGlobal("fetch", fetchMock);
    render(<KeepSearch kind="publications" filters={{ q: "solar cells", year: "2024" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Email me new matches" }));
    fireEvent.change(screen.getByLabelText("Your email"), { target: { value: "me@example.org" } });
    fireEvent.click(screen.getByRole("button", { name: "Keep this search" }));
    expect(await screen.findByText(/open the message sent to me@example.org and confirm/)).toBeInTheDocument();
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      email: "me@example.org", kind: "publications", filters: { q: "solar cells", year: "2024" },
    });
  });
});
