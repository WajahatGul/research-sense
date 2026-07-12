import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchResearchers, fetchResearcher } from "../api/researchers";
import { PageHeader } from "../components/PageHeader";
import { Loader, ErrorState } from "../components/StateViews";
import { NetworkView } from "../features/collaboration/NetworkView";
import styles from "./Collaboration.module.css";

type CampusFilter = "all" | "same" | "cross";

export default function Collaboration() {
  const [selected, setSelected] = useState<number | null>(null);
  const [campusFilter, setCampusFilter] = useState<CampusFilter>("all");
  const [areaFilter, setAreaFilter] = useState<string>("");

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

  const all = detail?.collaborators ?? [];

  // Areas available to filter by: everything shared with any collaborator.
  const areaOptions = useMemo(() => {
    const set = new Set<string>();
    all.forEach((c) => c.shared_topics.forEach((t) => set.add(t)));
    return [...set].sort();
  }, [all]);

  const filtered = useMemo(() => {
    return all
      .filter((c) =>
        campusFilter === "all"
          ? true
          : campusFilter === "same"
            ? c.same_campus
            : !c.same_campus)
      .filter((c) => (areaFilter ? c.shared_topics.includes(areaFilter) : true))
      .slice(0, 6);
  }, [all, campusFilter, areaFilter]);

  const CAMPUS_TABS: { key: CampusFilter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "same", label: "Same campus" },
    { key: "cross", label: "Cross-campus" },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Who to work with"
        title="Collaboration finder"
        description="Pick a researcher to see who they could collaborate with — proven past co-authors first, then people who share the most research areas. Gold-ringed nodes are cross-campus."
      >
        <select
          className={styles.select}
          value={activeId ?? ""}
          onChange={(e) => {
            setSelected(Number(e.target.value));
            setAreaFilter("");
          }}
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

        {detail && all.length > 0 && (
          <>
            <div className={styles.filters}>
              <div className={styles.tabs}>
                {CAMPUS_TABS.map((t) => (
                  <button
                    key={t.key}
                    className={`${styles.tab} ${
                      campusFilter === t.key ? styles.tabActive : ""
                    }`}
                    onClick={() => setCampusFilter(t.key)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
              {areaOptions.length > 0 && (
                <select
                  className={styles.areaSelect}
                  value={areaFilter}
                  onChange={(e) => setAreaFilter(e.target.value)}
                  aria-label="Filter by research area"
                >
                  <option value="">All research areas</option>
                  {areaOptions.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {filtered.length > 0 ? (
              <NetworkView
                centerName={detail.full_name}
                collaborators={filtered}
              />
            ) : (
              <p className={styles.none}>
                No collaborators match these filters. Try widening them.
              </p>
            )}
          </>
        )}

        {detail && all.length === 0 && (
          <p className={styles.none}>
            No shared-area or co-authored collaborators found for{" "}
            {detail.full_name} yet.
          </p>
        )}
      </div>
    </>
  );
}
