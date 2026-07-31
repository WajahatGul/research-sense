import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  fetchResearchers,
  fetchResearcher,
  fetchCollaborators,
  type CollabSort,
} from "../api/researchers";
import { PageHeader } from "../components/PageHeader";
import { Loader, ErrorState } from "../components/StateViews";
import { NetworkView } from "../features/collaboration/NetworkView";
import styles from "./Collaboration.module.css";

type CampusFilter = "all" | "same" | "cross";

const SORTS: { key: CollabSort; label: string }[] = [
  { key: "relevance", label: "Most relevant" },
  { key: "shared_areas", label: "Shared research areas" },
  { key: "coauthored", label: "Co-authored papers" },
  { key: "name", label: "Name A–Z" },
  { key: "campus", label: "Campus" },
];

export default function Collaboration() {
  const [selected, setSelected] = useState<number | null>(null);
  const [campusFilter, setCampusFilter] = useState<CampusFilter>("all");
  const [areaFilter, setAreaFilter] = useState<string>("");
  const [sort, setSort] = useState<CollabSort>("relevance");

  const { data: list } = useQuery({
    queryKey: ["researchers", "collab-picker"],
    queryFn: () => fetchResearchers({ page_size: 100 }),
  });

  const activeId = selected ?? list?.items[0]?.researcher_id ?? null;

  const {
    data: detail,
    isLoading: detailLoading,
    isError: detailError,
  } = useQuery({
    queryKey: ["researcher", activeId],
    queryFn: () => fetchResearcher(activeId as number),
    enabled: activeId != null,
  });

  const {
    data: collabRows,
    isLoading: collabLoading,
    isError: collabError,
  } = useQuery({
    queryKey: ["collaborators", activeId, sort],
    queryFn: () => fetchCollaborators(activeId as number, sort),
    enabled: activeId != null,
    // Keep showing the previous rows across a sort change (smooth re-sort),
    // but NOT across a researcher change — otherwise the new researcher's
    // name would render alongside the old researcher's stale collaborators
    // (or a false "no collaborators" empty state, if the old researcher had
    // none). Only reuse the placeholder when it came from the same activeId.
    placeholderData: (prev, prevQuery) =>
      prevQuery?.queryKey[1] === activeId ? prev : undefined,
  });

  const isLoading = detailLoading || collabLoading;
  const isError = detailError || collabError;

  const all = collabRows ?? [];

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
      .slice(0, 8);
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

        {detail && collabRows !== undefined && all.length > 0 && (
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
              <select
                className={styles.areaSelect}
                value={sort}
                onChange={(e) => setSort(e.target.value as CollabSort)}
                aria-label="Sort collaborators"
              >
                {SORTS.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </select>
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

        {detail && collabRows !== undefined && all.length === 0 && (
          <p className={styles.none}>
            No shared-area or co-authored collaborators found for{" "}
            {detail.full_name} yet.
          </p>
        )}
      </div>
    </>
  );
}
