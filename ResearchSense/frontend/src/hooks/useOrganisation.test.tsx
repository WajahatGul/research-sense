import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { fetchOrganisation } from "../api/organisation";
import { useTerms } from "./useOrganisation";

vi.mock("../api/organisation", () => ({ fetchOrganisation: vi.fn() }));

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useTerms", () => {
  it("speaks a university's words until told otherwise", () => {
    vi.mocked(fetchOrganisation).mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useTerms(), { wrapper });
    expect(result.current).toMatchObject({ site: "campus", sites: "campuses", unit: "department" });
  });

  it("speaks a company's words for a company", async () => {
    vi.mocked(fetchOrganisation).mockResolvedValue({
      name: "Northwind Labs", kind: "company", noun: "company", people: "Experts",
      unit: "Team", site: "Site", document_types: [],
    });
    const { result } = renderHook(() => useTerms(), { wrapper });
    await waitFor(() => expect(result.current.sites).toBe("sites"));
    expect(result.current).toMatchObject({ Site: "Site", units: "teams", people: "experts" });
  });
});
