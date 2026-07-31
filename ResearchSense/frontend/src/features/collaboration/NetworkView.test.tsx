import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { CollaborationSuggestion } from "../../types";
import { NetworkView } from "./NetworkView";

function makeCollaborator(
  overrides: Partial<CollaborationSuggestion> & { researcher_id: number },
): CollaborationSuggestion {
  return {
    full_name: `Researcher ${overrides.researcher_id}`,
    designation: "Assistant Professor",
    department: "Computer Science",
    campus: "Islamabad (E-8)",
    similarity_score: 0.5,
    shared_topics: [],
    shared_count: 1,
    copublications: 0,
    past_coauthor: false,
    same_campus: true,
    relevance: 0.5,
    international: false,
    ...overrides,
  };
}

function renderNetwork(centerName: string, collaborators: CollaborationSuggestion[]) {
  return render(
    <MemoryRouter>
      <NetworkView centerName={centerName} collaborators={collaborators} />
    </MemoryRouter>,
  );
}

describe("NetworkView", () => {
  it("renders the center researcher's initials", () => {
    const { container } = renderNetwork("Dr. Ayesha Khan", [
      makeCollaborator({ researcher_id: 1 }),
    ]);
    expect(container.textContent).toContain("AK");
  });

  it("renders at most 8 nodes when given 10 collaborators", () => {
    const collaborators = Array.from({ length: 10 }, (_, i) =>
      makeCollaborator({ researcher_id: i + 1, full_name: `Researcher ${i + 1}` }),
    );
    const { container } = renderNetwork("Dr. Ayesha Khan", collaborators);
    expect(container.querySelectorAll("ul > li")).toHaveLength(8);
  });

  it("shows the globe marker for an international collaborator", () => {
    const { container } = renderNetwork("Dr. Ayesha Khan", [
      makeCollaborator({ researcher_id: 1, international: true }),
    ]);
    expect(container.textContent).toContain("🌐");
  });

  it("gives a collaborator with copublications: 3 an edge stroke-width of 4", () => {
    const { container } = renderNetwork("Dr. Ayesha Khan", [
      makeCollaborator({ researcher_id: 1, past_coauthor: true, copublications: 3 }),
    ]);
    const line = container.querySelector("line");
    expect(line).not.toBeNull();
    expect(line?.getAttribute("stroke-width")).toBe("4");
  });
});
