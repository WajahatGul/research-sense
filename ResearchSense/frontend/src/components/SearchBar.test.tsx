import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fetchSuggestions } from "../api/suggest";
import { SearchBar } from "./SearchBar";

vi.mock("../api/suggest", () => ({ fetchSuggestions: vi.fn() }));

function setup(onSearch = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<SearchBar suggest="all" onSearch={onSearch} />} />
          <Route path="/researchers/:id" element={<p>profile page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return screen.getByRole("combobox");
}

describe("SearchBar suggestions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchSuggestions).mockResolvedValue([
      { kind: "researcher", id: 8, label: "Arif Ur Rahman", detail: "Professor · Computer Science" },
      { kind: "publication", id: 5371, label: "Database Preservation", detail: "2015" },
    ]);
  });

  it("lists matches after two letters", async () => {
    const input = setup();
    fireEvent.change(input, { target: { value: "ari" } });
    expect(await screen.findByRole("option", { name: /Arif Ur Rahman/ })).toBeTruthy();
    expect(input.getAttribute("aria-expanded")).toBe("true");
  });

  it("suggests nothing for a single letter", async () => {
    const input = setup();
    fireEvent.change(input, { target: { value: "a" } });
    await new Promise((r) => setTimeout(r, 250));
    expect(fetchSuggestions).not.toHaveBeenCalled();
    expect(screen.queryByRole("option")).toBeNull();
  });

  it("opens a person's profile with the keyboard", async () => {
    const input = setup();
    fireEvent.change(input, { target: { value: "ari" } });
    await screen.findByRole("option", { name: /Arif Ur Rahman/ });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText("profile page")).toBeTruthy();
  });

  it("searches for the exact title when a paper is picked", async () => {
    const onSearch = vi.fn();
    const input = setup(onSearch);
    fireEvent.change(input, { target: { value: "data" } });
    fireEvent.mouseDown(await screen.findByRole("option", { name: /Database Preservation/ }));
    expect(onSearch).toHaveBeenCalledWith("Database Preservation");
  });

  it("Escape closes the list", async () => {
    const input = setup();
    fireEvent.change(input, { target: { value: "ari" } });
    await screen.findByRole("option", { name: /Arif Ur Rahman/ });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(input.getAttribute("aria-expanded")).toBe("false");
  });
});
