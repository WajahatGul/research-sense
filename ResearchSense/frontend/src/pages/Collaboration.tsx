import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { Researcher } from "../types";
import {
  fetchResearchers,
  fetchResearcher,
  fetchCollaborators,
  type CollabSort,
} from "../api/researchers";
import { PageHeader } from "../components/PageHeader";
import { Loader, ErrorState, EmptyState } from "../components/StateViews";
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
  const [selectedName, setSelectedName] = useState<string>("");
  const [campusFilter, setCampusFilter] = useState<CampusFilter>("all");
  const [areaFilter, setAreaFilter] = useState<string>("");
  const [sort, setSort] = useState<CollabSort>("relevance");

  const selectResearcher = (r: Researcher) => {
    setSelected(r.researcher_id);
    setSelectedName(r.full_name);
    setAreaFilter("");
  };

  const activeId = selected;

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
        description="Pick a researcher to see who they could collaborate with — proven past co-authors first, then people who share the most research areas. Gold-ringed nodes are cross-campus; 🌐 marks researchers who have published with institutions abroad."
      >
        <ResearcherTypeahead
          selectedName={selectedName}
          onSelect={selectResearcher}
        />
      </PageHeader>

      <div className={`container ${styles.body}`}>
        {activeId == null && (
          <EmptyState message="Pick a researcher to see who they could collaborate with." />
        )}

        {activeId != null && isLoading && <Loader />}
        {activeId != null && isError && <ErrorState />}

        {activeId != null && detail && collabRows !== undefined && all.length > 0 && (
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
                centerId={detail.researcher_id}
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

        {activeId != null && detail && collabRows !== undefined && all.length === 0 && (
          <p className={styles.none}>
            No shared-area or co-authored collaborators found for{" "}
            {detail.full_name} yet.
          </p>
        )}
      </div>
    </>
  );
}

interface TypeaheadProps {
  selectedName: string;
  onSelect: (r: Researcher) => void;
}

const MIN_QUERY_LENGTH = 2;
const DEBOUNCE_MS = 250;

// Simple, dependency-free typeahead: SERVER-SIDE search (the roster is 358+
// researchers and growing — filtering a single preloaded page misses
// everyone outside it) via GET /api/researchers?q=..., debounced ~250ms so
// a keystroke doesn't fire a request each time. Lets the user pick a match
// with the mouse or the keyboard (Up/Down/Enter/Escape). No combobox lib.
function ResearcherTypeahead({ selectedName, onSelect }: TypeaheadProps) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(-1);
  const blurTimeout = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedQuery(query.trim()), DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [query]);

  // Reflect an externally-chosen researcher in the box, but only when the
  // selection actually changes — so the user can freely delete what they typed
  // without it being re-filled on every keystroke.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sync the input to an external selection change, not a render loop.
    setQuery(selectedName);
  }, [selectedName]);

  const searchReady = debouncedQuery.length >= MIN_QUERY_LENGTH;

  const {
    data: results,
    isFetching,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["researcher-search", debouncedQuery],
    queryFn: () => fetchResearchers({ q: debouncedQuery, page_size: 8 }),
    enabled: searchReady,
  });

  const matches = results?.items ?? [];

  const pick = (r: Researcher) => {
    onSelect(r);
    setQuery(r.full_name);
    setOpen(false);
  };

  return (
    <div className={styles.typeahead}>
      <input
        type="search"
        className={styles.searchInput}
        aria-label="Search researchers by name"
        placeholder="Type a researcher's name…"
        role="combobox"
        aria-expanded={open && searchReady}
        aria-controls="researcher-typeahead-listbox"
        aria-activedescendant={
          open && matches[highlighted]
            ? `researcher-option-${matches[highlighted].researcher_id}`
            : undefined
        }
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setHighlighted(-1);
        }}
        onBlur={() => {
          // Let a click/mousedown on an option register before we close.
          blurTimeout.current = setTimeout(() => setOpen(false), 120);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setHighlighted((i) => Math.min(i + 1, matches.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setHighlighted((i) => Math.max(i - 1, -1));
          } else if (e.key === "Enter") {
            e.preventDefault();
            const match = matches[highlighted];
            if (match) pick(match);
          } else if (e.key === "Escape") {
            setQuery("");
            setDebouncedQuery("");
            setOpen(false);
          }
        }}
      />
      {open && searchReady && isError && (
        <p className={styles.pickerError}>
          Could not load researchers.{" "}
          <button
            type="button"
            className={styles.retryButton}
            onClick={() => refetch()}
          >
            Retry
          </button>
        </p>
      )}
      {open && searchReady && !isError && isFetching && (
        <p className={styles.noMatch}>Searching…</p>
      )}
      {open && searchReady && !isError && !isFetching && matches.length > 0 && (
        <ul
          id="researcher-typeahead-listbox"
          role="listbox"
          className={styles.listbox}
        >
          {matches.map((r, i) => (
            <li
              key={r.researcher_id}
              id={`researcher-option-${r.researcher_id}`}
              role="option"
              aria-selected={i === highlighted}
              className={i === highlighted ? styles.optionActive : styles.option}
              onMouseDown={(e) => {
                e.preventDefault();
                if (blurTimeout.current) clearTimeout(blurTimeout.current);
                pick(r);
              }}
            >
              {r.full_name} — {r.designation}
            </li>
          ))}
        </ul>
      )}
      {open && searchReady && !isError && !isFetching && matches.length === 0 && (
        <p className={styles.noMatch}>
          No researcher found matching '{debouncedQuery}'.
        </p>
      )}
    </div>
  );
}
