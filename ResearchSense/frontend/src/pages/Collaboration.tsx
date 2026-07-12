import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchResearchers, fetchResearcher } from "../api/researchers";
import { PageHeader } from "../components/PageHeader";
import { Loader, ErrorState } from "../components/StateViews";
import { NetworkView } from "../features/collaboration/NetworkView";
import styles from "./Collaboration.module.css";

export default function Collaboration() {
  const [selected, setSelected] = useState<number | null>(null);

  const { data: list } = useQuery({
    queryKey: ["researchers", "collab-picker"],
    queryFn: () => fetchResearchers({ page_size: 100 }),
  });

  const activeId = selected ?? list?.items[0]?.researcher_id ?? null;

  const { data: detail, isLoading, isError } = useQuery({
    queryKey: ["researcher", activeId],
    queryFn: () => fetchResearcher(activeId as number),
    enabled: activeId != null,
  });

  return (
    <>
      <PageHeader
        eyebrow="Who to work with"
        title="Collaboration finder"
        description="Pick a researcher to see who they could collaborate with, ranked by how many research areas they share. Gold-ringed nodes are cross-campus matches."
      >
        <select
          className={styles.select}
          value={activeId ?? ""}
          onChange={(e) => setSelected(Number(e.target.value))}
          aria-label="Select a researcher"
        >
          {list?.items.map((r) => (
            <option key={r.researcher_id} value={r.researcher_id}>
              {r.full_name} — {r.designation}
            </option>
          ))}
        </select>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        {isLoading && <Loader />}
        {isError && <ErrorState />}
        {detail && detail.collaborators.length > 0 && (
          <NetworkView
            centerName={detail.full_name}
            collaborators={detail.collaborators}
          />
        )}
        {detail && detail.collaborators.length === 0 && (
          <p className={styles.none}>
            No shared-topic collaborators found for {detail.full_name} yet.
          </p>
        )}
      </div>
    </>
  );
}
