import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatPanel } from "./ChatPanel";

vi.mock("../../api/chat", () => ({
  fetchChatSuggestions: vi.fn().mockResolvedValue([]),
  sendChat: vi.fn(),
}));
vi.mock("../../api/library", () => ({ fetchLibrary: vi.fn().mockResolvedValue([]) }));
vi.mock("../../api/workspace", () => ({ getWorkspaceSession: () => null }));

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.search}</output>;
}

function renderAt(url: string, prefillFromUrl = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <ChatPanel prefillFromUrl={prefillFromUrl} />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => localStorage.clear());

describe("ChatPanel and the page URL", () => {
  it("leaves another page's search and filters alone (the floating widget)", async () => {
    renderAt("/researchers?q=ayesha&campus=Karachi");

    await waitFor(() => screen.getByPlaceholderText(/Ask a question/));
    expect(screen.getByTestId("location").textContent).toBe("?q=ayesha&campus=Karachi");
    expect(screen.getByPlaceholderText<HTMLTextAreaElement>(/Ask a question/).value).toBe("");
  });

  it("prefills the box from ?q= on the /ask page and removes only that parameter", async () => {
    renderAt("/ask?q=Who%20works%20on%20energy%3F&ref=library", true);

    await waitFor(() =>
      expect(
        screen.getByPlaceholderText<HTMLTextAreaElement>(/Ask a question/).value,
      ).toBe("Who works on energy?"),
    );
    expect(screen.getByTestId("location").textContent).toBe("?ref=library");
  });
});
