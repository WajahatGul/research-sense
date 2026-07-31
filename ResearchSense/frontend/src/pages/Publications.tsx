import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";

import { fetchPublications, fetchPublicationYears } from "../api/publications";
import { fetchCampuses, fetchDepartments } from "../api/researchers";
import { PageHeader } from "../components/PageHeader";
import { SearchBar } from "../components/SearchBar";
import { PublicationItem } from "../components/PublicationItem";
import { Pagination } from "../components/Pagination";
import { Loader, ErrorState, EmptyState } from "../components/StateViews";
import styles from "./Publications.module.css";

const PAGE_SIZE = 10;

interface Filters {
  q: string;
  year: string;
  campus: string;
  department: string;
  publicationType: string;
  dateFrom: string;
  dateTo: string;
}

const blankFilters: Filters = {
  q: "",
  year: "",
  campus: "",
  department: "",
  publicationType: "",
  dateFrom: "",
  dateTo: "",
};

export default function Publications() {
  const [params] = useSearchParams();
  const topicId = params.get("topic_id");

  // Seed the search from the URL so other pages (e.g. chat source chips)
  // can deep-link straight to a title. A deep link counts as an implicit
  // search, so it runs immediately instead of waiting for the button.
  const initialQ = params.get("q") ?? "";
  const [pending, setPending] = useState<Filters>({ ...blankFilters, q: initialQ });
  const [applied, setApplied] = useState<Filters | null>(() =>
    initialQ || topicId ? { ...blankFilters, q: initialQ } : null,
  );
  const [page, setPage] = useState(1);

  const hasSearched = applied !== null;

  const { data: years } = useQuery({
    queryKey: ["pub-years"],
    queryFn: fetchPublicationYears,
  });
  const { data: campuses } = useQuery({
    queryKey: ["campuses"],
    queryFn: fetchCampuses,
  });
  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: fetchDepartments,
  });

  const { data, isLoading, isError } = useQuery({
    queryKey: ["publications", applied, topicId, page],
    queryFn: () => {
      const f = applied ?? blankFilters;
      return fetchPublications({
        q: f.q,
        year: f.year ? Number(f.year) : undefined,
        campus: f.campus || undefined,
        department: f.department || undefined,
        publication_type: f.publicationType
          ? (f.publicationType as "journal" | "conference")
          : undefined,
        date_from: f.dateFrom || undefined,
        date_to: f.dateTo || undefined,
        topic_id: topicId ? Number(topicId) : undefined,
        page,
        page_size: PAGE_SIZE,
      });
    },
    enabled: hasSearched,
    placeholderData: keepPreviousData,
  });

  const runSearch = (overrides?: Partial<Filters>) => {
    const next = overrides ? { ...pending, ...overrides } : pending;
    if (overrides) setPending(next);
    setApplied(next);
    setPage(1);
  };

  return (
    <>
      <PageHeader
        eyebrow="Research output"
        title="Publications"
        description="Journal articles and conference papers from researchers across all campuses."
      >
        <div className={styles.controls}>
          <div className={styles.search}>
            <SearchBar
              placeholder="Search publication titles…"
              defaultValue={pending.q}
              onSearch={(v) => runSearch({ q: v })}
              hideButton
            />
          </div>
          <select
            className={styles.select}
            value={pending.campus}
            onChange={(e) => setPending((p) => ({ ...p, campus: e.target.value }))}
            aria-label="Filter by campus"
          >
            <option value="">All campuses</option>
            {campuses?.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            className={styles.select}
            value={pending.year}
            onChange={(e) => setPending((p) => ({ ...p, year: e.target.value }))}
            aria-label="Filter by year"
          >
            <option value="">All years</option>
            {years?.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
          <select
            className={styles.select}
            value={pending.department}
            onChange={(e) => setPending((p) => ({ ...p, department: e.target.value }))}
            aria-label="Filter by department"
          >
            <option value="">All departments</option>
            {departments?.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <select
            className={styles.select}
            value={pending.publicationType}
            onChange={(e) =>
              setPending((p) => ({ ...p, publicationType: e.target.value }))
            }
            aria-label="Filter by paper type"
          >
            <option value="">All paper types</option>
            <option value="journal">Journal papers</option>
            <option value="conference">Conference papers</option>
          </select>
          <div className={styles.dateGroup}>
            <div className={styles.dateField}>
              <label className={styles.dateLabel} htmlFor="pub-date-from">
                From date
              </label>
              <input
                id="pub-date-from"
                type="date"
                className={styles.dateInput}
                value={pending.dateFrom}
                onChange={(e) =>
                  setPending((p) => ({ ...p, dateFrom: e.target.value }))
                }
                aria-label="From date"
              />
            </div>
            <div className={styles.dateField}>
              <label className={styles.dateLabel} htmlFor="pub-date-to">
                To date
              </label>
              <input
                id="pub-date-to"
                type="date"
                className={styles.dateInput}
                value={pending.dateTo}
                onChange={(e) => setPending((p) => ({ ...p, dateTo: e.target.value }))}
                aria-label="To date"
              />
            </div>
          </div>
          <button
            type="button"
            className={styles.searchButton}
            onClick={() => runSearch()}
            aria-label="Search publications"
          >
            Search
          </button>
        </div>
        <p className={styles.dateHint}>
          Papers before 2026 are recorded by year; they match from January 1.
        </p>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        {hasSearched && (
          <span className={`mono ${styles.count}`}>
            {(data?.total ?? 0).toLocaleString()} publications
          </span>
        )}

        {!hasSearched && (
          <EmptyState message="Choose your filters and press Search to see publications." />
        )}
        {hasSearched && isLoading && <Loader />}
        {hasSearched && isError && <ErrorState />}
        {hasSearched && data && data.items.length === 0 && (
          <EmptyState message="No publications match your search." />
        )}
        {hasSearched && data && data.items.length > 0 && (
          <div className={styles.list}>
            {data.items.map((p) => (
              <PublicationItem key={p.publication_id} pub={p} />
            ))}
          </div>
        )}

        {hasSearched && data && (
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={data.total}
            onChange={setPage}
          />
        )}
      </div>
    </>
  );
}
