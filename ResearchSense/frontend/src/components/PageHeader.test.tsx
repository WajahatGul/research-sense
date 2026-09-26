import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageHeader } from "./PageHeader";

describe("PageHeader", () => {
  it("names the page in the browser tab, not just the site", () => {
    render(<PageHeader eyebrow="Directory" title="Researchers" />);
    expect(document.title).toBe("Researchers · ResearchSense");
  });
});
