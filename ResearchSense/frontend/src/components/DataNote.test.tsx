import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DataNote } from "./DataNote";

describe("DataNote", () => {
  it("renders its children text", () => {
    render(<DataNote>This is a coverage note.</DataNote>);
    expect(screen.getByText("This is a coverage note.")).toBeInTheDocument();
  });
});
