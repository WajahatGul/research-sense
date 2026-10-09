import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { clearToken, setToken } from "../api/auth";
import Header from "./Header";

// An unsigned token with the given role: the header only reads the role to
// label the link; the server verifies the real token on every request.
const token = (role: string) => `x.${btoa(JSON.stringify({ sub: "s", role }))}.y`;

function renderHeader() {
  render(
    <MemoryRouter initialEntries={["/researchers"]}>
      <Header />
    </MemoryRouter>,
  );
}

describe("Header", () => {
  afterEach(() => localStorage.clear());

  it("offers sign-in to a visitor", () => {
    renderHeader();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/portal");
  });

  it("updates the moment an admin signs in, and points to the admin panel", () => {
    renderHeader();
    act(() => setToken(token("admin")));
    expect(screen.getByRole("link", { name: "Admin panel" })).toHaveAttribute(
      "href",
      "/staff-access",
    );
    act(() => clearToken());
    expect(screen.getByRole("link", { name: "Sign in" })).toBeInTheDocument();
  });

  it("points a researcher to their portal", () => {
    localStorage.setItem("rs_token", token("researcher"));
    renderHeader();
    expect(screen.getByRole("link", { name: "Your portal" })).toHaveAttribute("href", "/portal");
  });
});
