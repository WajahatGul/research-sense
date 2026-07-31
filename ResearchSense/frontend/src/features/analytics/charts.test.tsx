import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DepartmentBars, InternationalTrend } from "./charts";

describe("DepartmentBars", () => {
  it("renders without crashing on empty data", () => {
    const { container } = render(<DepartmentBars data={[]} />);
    expect(container).toBeInTheDocument();
  });

  it("renders at most 10 departments", () => {
    const rows = Array.from({ length: 14 }, (_, i) => ({
      department: `Dept ${i}`, researchers: 1, publications: 14 - i, citations: 0,
    }));
    const { container } = render(<DepartmentBars data={rows} />);
    expect(container.textContent).not.toContain("Dept 13");
  });
});

describe("InternationalTrend", () => {
  it("renders both series names in the legend", () => {
    const { container } = render(
      <InternationalTrend data={[{ year: 2020, international: 2, domestic: 5 }]} />,
    );
    expect(container.textContent?.toLowerCase()).toContain("international");
    expect(container.textContent?.toLowerCase()).toContain("domestic");
  });
});
